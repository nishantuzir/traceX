# src/tracex/cli/cli.py

import click
import os
import sys
from ..lineage_extractor.extractor import DbtColumnLineageExtractor
from ..report.generator import TraceXReportGenerator
from importlib.metadata import version, PackageNotFoundError

TRACEX_LOGO = r"""
 _______  _______  _______  _______  _______  _______ 
|__   __||__   __||__   __||__   __||__   __||__   __|
   | |      | |      | |      | |      | |      | |    
   | |      | |      | |      | |      | |      | |    
   | |      | |      | |      | |      | |      | |    
   |_|      |_|      |_|      |_|      |_|      |_|    
"""

try:
    __version__ = version("tracex")
except PackageNotFoundError:
    __version__ = "unknown"

@click.group()
@click.version_option(__version__, prog_name="tracex")
def cli():
    click.echo(f"{TRACEX_LOGO}\n")
    click.echo("Welcome to TraceX - Column Lineage Tool")
    """TraceX CLI tool"""
    pass

@cli.command("generate")
@click.option(
    "--output-dir",
    type=str,
    default="dist",
    help="Directory to save both JSON and HTML files (default: dist)"
)
@click.option(
    "--manifest",
    type=str,
    default="target/manifest.json",
    help="Path to dbt manifest.json file (default: target/manifest.json)"
)
@click.option(
    "--catalog", 
    type=str,
    default="target/catalog.json",
    help="Path to dbt catalog.json file (default: target/catalog.json)"
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug-level logging"
)
@click.option(
    "--light",
    is_flag=True,
    default=False,
    help="Enable light mode (excludes compiled_code from output for smaller file size)"
)

def generate_report(output_dir, manifest, catalog, debug, light):
    """Generate a TraceX lineage report with both JSON and HTML output."""
    import logging
    from ..utils import log

    try:
       

        # Set up logging based on flag
        log_level = logging.DEBUG if debug else logging.INFO
        logger = log.setup_logging(level=log_level)

        if not os.path.exists(manifest):
            logger.error(f"ERROR: Manifest file not found at {manifest}")
            sys.exit(1)
        if not os.path.exists(catalog):
            logger.error(f"ERROR: Catalog file not found at {catalog}")
            sys.exit(1)

        logger.info("Loading dbt manifest and catalog...")
        extractor = DbtColumnLineageExtractor(manifest, catalog)

        # --- Log version info (matches what will end up in metadata) ---
        manifest_meta = extractor.manifest.get("metadata", {})
        adapter = manifest_meta.get("adapter_type", "unknown")
        dbt_version = manifest_meta.get("dbt_version", "unknown")
        project = manifest_meta.get("project_name", "unknown")

        logger.info(
            "Running with configuration:\n"
            f"         TraceX version     : {extractor.tracex_version}\n"
            f"         dbt version        : {dbt_version}\n"
            f"         SQL dialect        : {adapter}\n"
            f"         dbt project        : {project}"
        )

        logger.info("Extracting lineage data...")
        report_generator = TraceXReportGenerator(extractor, light_mode=light)

        logger.info("Generating report...")
        report_generator.generate_report(output_dir=output_dir)
        click.echo("\n")
        click.echo("SUCCESS: Report completed!")
        click.echo(f"  JSON: {output_dir}/tracex-manifest.json")
        click.echo(f"  HTML: {output_dir}/index.html")
        sys.exit(0)
    except Exception as e:
        logger.error(f"ERROR: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
