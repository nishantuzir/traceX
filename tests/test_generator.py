from tracex.report.generator import TraceXReportGenerator
from tracex.lineage_extractor.extractor import DbtColumnLineageExtractor
from test_utils import count_manifest_objects, count_edges_with_double_colon
import pytest

def test_build_manifest_node_data_node_not_found(dbt_valid_test_data_dir):
    """Test build_manifest_node_data when node_id is not found in manifest or catalog."""
    
    # Create an extractor instance
    if dbt_valid_test_data_dir is None:
        pytest.skip("No valid versioned test data present")
    extractor = DbtColumnLineageExtractor(
        manifest_path=f"{dbt_valid_test_data_dir}/manifest.json",
        catalog_path=f"{dbt_valid_test_data_dir}/catalog.json"
    )
    
    # Create a report generator instance
    report_generator = TraceXReportGenerator(extractor)
    
    # Test with a non-existent node_id
    non_existent_node_id = "model.does_not_exist.fake_model"
    
    # Call build_manifest_node_data with non-existent node
    node_data = report_generator.build_manifest_node_data(non_existent_node_id)
    
    # Verify the result structure when node is not found
    expected_structure = {
        "nodeType": "unknown",
        "rawCode": None,
        "compiledCode": None,
        "materialized": None,
        "path": None,
        "database": None,
        "schema": None,
        "description": None,
        "contractEnforced": None,
        "refs": [],
        "columns": {},
    }
    
    assert node_data == expected_structure
    assert node_data["nodeType"] == "unknown"
    assert node_data["rawCode"] is None
    assert node_data["compiledCode"] is None
    assert node_data["schema"] is None
    assert node_data["description"] is None
    assert node_data["contractEnforced"] is None
    assert node_data["refs"] == []
    assert node_data["columns"] == {}


def test_detect_model_type_with_non_existent_node(dbt_valid_test_data_dir):
    """Test detect_model_type with a non-existent node_id."""
    
    if dbt_valid_test_data_dir is None:
        pytest.skip("No valid versioned test data present")
    extractor = DbtColumnLineageExtractor(
        manifest_path=f"{dbt_valid_test_data_dir}/manifest.json",
        catalog_path=f"{dbt_valid_test_data_dir}/catalog.json"
    )
    
    report_generator = TraceXReportGenerator(extractor)
    
    # Test with various non-existent node patterns
    test_cases = [
        ("model.does_not_exist.fake_model", "unknown"),
        ("model.does_not_exist.dim_fake", "dimension"),
        ("model.does_not_exist.fact_fake", "fact"),
        ("model.does_not_exist.int_fake", "intermediate"),
        ("model.does_not_exist.stg_fake", "staging"),
        ("completely.malformed.node.id", "unknown"),
        ("", "unknown"),
    ]
    
    for node_id, expected_type in test_cases:
        result = report_generator.detect_model_type(node_id)
        assert result == expected_type, f"Expected {expected_type} for {node_id}, got {result}"


def test_ensure_node_with_missing_node_creates_default(dbt_valid_test_data_dir):
    """Test that ensure_node creates a default node structure when node is missing."""
    from unittest.mock import patch
    
    if dbt_valid_test_data_dir is None:
        pytest.skip("No valid versioned test data present")
    extractor = DbtColumnLineageExtractor(
        manifest_path=f"{dbt_valid_test_data_dir}/manifest.json",
        catalog_path=f"{dbt_valid_test_data_dir}/catalog.json"
    )
    
    report_generator = TraceXReportGenerator(extractor)
    
    # Mock extract_project_lineage to return lineage data that references a non-existent node
    with patch.object(extractor, 'extract_project_lineage') as mock_extract:
        mock_extract.return_value = {
            "lineage": {
                "parents": {
                    "model.exists.child": {
                        "col1": [
                            {"dbt_node": "model.does_not_exist.parent", "column": "col1"}
                        ]
                    }
                },
                "children": {}
            }
        }
        
        # Build lineage - this should create the missing node with default values
        result = report_generator.build_full_lineage()
        
        # Verify both nodes exist in the result
        assert "model.exists.child" in result["nodes"]
        assert "model.does_not_exist.parent" in result["nodes"]
        
        # Verify the missing node has default structure
        missing_node = result["nodes"]["model.does_not_exist.parent"]
        assert missing_node["nodeType"] == "unknown"
        assert missing_node["modelType"] == "unknown"  # Since it doesn't match any prefix
        assert missing_node["rawCode"] is None
        assert missing_node["compiledCode"] is None
        assert missing_node["schema"] is None
        assert missing_node["description"] is None
        assert missing_node["columns"] == {}
        
        # Verify the edge was still created
        assert len(result["lineage"]["edges"]) > 0
        edge_found = False
        for edge in result["lineage"]["edges"]:
            if (edge["source"] == "model.does_not_exist.parent" and 
                edge["target"] == "model.exists.child"):
                edge_found = True
                break
        assert edge_found, "Expected edge between non-existent parent and child"

def test_generated_report_excludes_test_nodes(dbt_valid_test_data_dir):
    """Ensure test nodes are excluded and non-test resource types are present."""

    if dbt_valid_test_data_dir is None:
        pytest.skip("No valid versioned test data present")
    manifest_path = f"{dbt_valid_test_data_dir}/manifest.json"
    catalog_path = f"{dbt_valid_test_data_dir}/catalog.json"

    extractor = DbtColumnLineageExtractor(
        manifest_path=manifest_path,
        catalog_path=catalog_path
    )
    report_generator = TraceXReportGenerator(extractor)
    result = report_generator.build_full_lineage()
    nodes = result.get("nodes", {})
    assert nodes, "No nodes found in generated report"

    # Assert no test nodes exist
    for node_id, node_data in nodes.items():
        assert not node_id.startswith("test."), f"Test node found by ID: {node_id}"
        assert node_data.get("nodeType") != "test", f"Test node found by type: {node_id}"

    # Assert that we have some known non-test node types in the result
    expected_types = {"model", "source"}
    found_types = {node["nodeType"] for node in nodes.values()}

    missing_types = expected_types - found_types
    assert not missing_types, f"Missing expected node types: {missing_types}"


def test_manifest_vs_tracex_manifest_node_counts(dbt_valid_test_data_dir):
    """
    Test that validates node counts between original manifest and generated tracex manifest.
    
    Assertions:
    1. manifest_total == tracex_manifest_total (excluding test nodes and hardcoded nodes)
    2. manifest by_resource_type vs tracex nodes_by_type have same counts for models & sources
    3. there is exactly 1 hardcoded node in the tracex manifest
    """
    if dbt_valid_test_data_dir is None:
        pytest.skip("No valid versioned test data present")

    manifest_path = f"{dbt_valid_test_data_dir}/manifest.json"
    catalog_path = f"{dbt_valid_test_data_dir}/catalog.json"

    # Create extractor and report generator
    extractor = DbtColumnLineageExtractor(
        manifest_path=manifest_path,
        catalog_path=catalog_path
    )
    report_generator = TraceXReportGenerator(extractor)
    
    # Generate the full lineage result
    result = report_generator.build_full_lineage()
    
    # Count manifest objects
    manifest_counts = count_manifest_objects(report_generator.manifest)
    print(f"\n=== Node Count Validation for {dbt_valid_test_data_dir} ===")
    
    # Count tracex manifest objects 
    tracex_counts = count_edges_with_double_colon(result)
    
    # Calculate totals (excluding test nodes from manifest, hardcoded nodes from tracex)
    manifest_total = (
        manifest_counts["sources_total"] + 
        manifest_counts["by_resource_type"].get("model", 0) + 
        manifest_counts["by_resource_type"].get("snapshot", 0)
    )
    tracex_manifest_total = tracex_counts["nodes_total"] - tracex_counts["hardcoded_nodes"]
    
    # Print comparison table
    print(f"{'Node Type':<15} | {'Manifest':<10} | {'TraceX':<10} | {'Match':<5}")
    print("-" * 50)
    
    # Models comparison
    manifest_models = manifest_counts["by_resource_type"].get("model", 0)
    tracex_models = tracex_counts["nodes_by_type"].get("model", 0)
    models_match = "PASS" if manifest_models == tracex_models else "FAIL"
    print(f"{'Models':<15} | {manifest_models:<10} | {tracex_models:<10} | {models_match:<5}")
    
    # Sources comparison  
    manifest_sources = manifest_counts["sources_total"]
    tracex_sources = tracex_counts["nodes_by_type"].get("source", 0)
    sources_match = "PASS" if manifest_sources == tracex_sources else "FAIL"
    print(f"{'Sources':<15} | {manifest_sources:<10} | {tracex_sources:<10} | {sources_match:<5}")
    
    # Snapshots comparison
    manifest_snapshots = manifest_counts["by_resource_type"].get("snapshot", 0)
    tracex_snapshots = tracex_counts["nodes_by_type"].get("snapshot", 0)
    snapshots_match = "PASS" if manifest_snapshots == tracex_snapshots else "FAIL"
    print(f"{'Snapshots':<15} | {manifest_snapshots:<10} | {tracex_snapshots:<10} | {snapshots_match:<5}")
    
    # Tests (should be excluded from tracex)
    manifest_tests = manifest_counts["by_resource_type"].get("test", 0)
    tracex_tests = tracex_counts["nodes_by_type"].get("test", 0)
    tests_excluded = "PASS" if tracex_tests == 0 else "FAIL"
    print(f"{'Tests':<15} | {manifest_tests:<10} | {tracex_tests:<10} | {tests_excluded:<5}")
    
    # Hardcoded nodes (only in tracex)
    hardcoded_nodes = tracex_counts["hardcoded_nodes"]
    hardcoded_ok = "PASS" if hardcoded_nodes == 1 else "FAIL"
    print(f"{'Hardcoded':<15} | {'N/A':<10} | {hardcoded_nodes:<10} | {hardcoded_ok:<5}")
    
    print("-" * 50)
    
    # Totals comparison
    total_match = "PASS" if manifest_total == tracex_manifest_total else "FAIL"
    print(f"{'TOTAL':<15} | {manifest_total:<10} | {tracex_manifest_total:<10} | {total_match:<5}")
    print("(excludes tests and hardcoded nodes)")
    print()
    
    # Assertion 1: Total counts should match (excluding test nodes and hardcoded nodes)
    assert manifest_total == tracex_manifest_total, (
        f"Manifest total ({manifest_total}) should equal tracex manifest total ({tracex_manifest_total}). "
        f"Manifest counts: {manifest_counts}, TraceX counts: {tracex_counts}"
    )
    
    # Assertion 2: Model and source counts should match
    assert manifest_models == tracex_models, (
        f"Model counts should match: manifest has {manifest_models}, tracex has {tracex_models}"
    )
    
    assert manifest_sources == tracex_sources, (
        f"Source counts should match: manifest has {manifest_sources}, tracex has {tracex_sources}"
    )
    
    # Assertion 3: There should be exactly 1 hardcoded node
    assert tracex_counts["hardcoded_nodes"] == 1, (
        f"Expected exactly 1 hardcoded node, but found {tracex_counts['hardcoded_nodes']}"
    )
    
    print("=" * 60)
