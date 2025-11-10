import click
import asyncio
from pathlib import Path
from rich.console import Console
from config.settings import TDAConfig
from analysis.workflow import TDAWorkflow
from visualization.plots import TDAVisualizer

console = Console()

@click.group()
def cli():
    """TDA Grid Analysis Tool"""
    pass

@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file')
@click.option('--fire-data', '-f', type=click.Path(exists=True), required=True, help='Fire data file')
@click.option('--output', '-o', type=click.Path(), help='Output directory')
@click.option('--visualize/--no-visualize', default=True, help='Generate visualizations')
def analyze(config, fire_data, output, visualize):
    """Run TDA analysis on grid data"""
    asyncio.run(_run_analysis(config, fire_data, output, visualize))

async def _run_analysis(config_path, fire_data_path, output_dir, visualize):
    # Load configuration
    if config_path:
        config = TDAConfig.parse_file(config_path)
    else:
        config = TDAConfig()
    
    # Run analysis
    workflow = TDAWorkflow(config)
    result = await workflow.run_full_analysis(Path(fire_data_path))
    
    if result.success:
        console.print(f"[green]Analysis completed successfully![/green]")
        console.print(f"Wasserstein Distance: {result.wasserstein_distance:.6f}")
        console.print(f"Features Before: {result.before_features}")
        console.print(f"Features After: {result.after_features}")
        console.print(f"Execution Time: {result.execution_time:.2f}s")
        
        if visualize:
            # Generate and save plots
            visualizer = TDAVisualizer()
            # Implementation for saving plots
            
    else:
        console.print(f"[red]Analysis failed: {result.error_message}[/red]")

if __name__ == '__main__':
    cli()