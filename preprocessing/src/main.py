import typer
from typing_extensions import Annotated
from rich.console import Console
from rich import print
from cli_markdown import print_table
import os
from protected_areas.wpda_wrapper import WDPAWrapper
from osm.osm_wrapper import OSMWrapper
from enrichment.lulc_enrichment_wrapper import LULCEnrichmentWrapper
from impedance.impedance_wrapper import ImpedanceWrapper
import time

# TODO - to add the function that can create impedance dataset based on csv table if user doesn't have it yet. So, the function can be used as option in 1,3 and 4th commands independently.
# TODO - to put recurring time captures to the separate function? (or use local module timing)
err_console = Console(stderr=True, style="bold red")

app = typer.Typer(
    name="Data4Land CLI",
    help="CLI tool for preprocessing and enriching land-use/land-cover data.",
)

#TODO make a config validator script
# e.g 
# if self.input_folder is None:
#     raise ValueError("LULC directory is null or not found in the configuration file.")


def check_file_exists(filePath:str):
    """
    Check if a file exists at a given path.

    Args:
        filePath (str): The path to the file.
    """
    if os.path.exists(filePath):
        fileName = os.path.basename(filePath).split(".")[0]
        print(f"[green] {fileName} File found! [/green] :white_check_mark:")
    else:
        err_console.print(f" File not found at {filePath}")
        raise typer.Exit(code=1)

#NOTE only prompt user to confirm using APIs.
@app.command("process-wdpa")
def process_wdpa(
    config_dir: Annotated[str, typer.Option(..., help="Directory with the configuration file")] = "./config",
    use_yearly_pa_raster: Annotated[bool, typer.Option("--enrich-single-year", "-e", help="use a specific PA year to update LULC or use all years")] = False,
    auto_confirm: Annotated[bool, typer.Option("--force", "-f", help="Auto confirm all prompts")] = False,
    skip_fetch: Annotated[bool, typer.Option("--skip-fetch", "-s", help="Skip fetching protected areas for existing country PA geojson (if data was already fetched from previous sessions)")] = False,
    delete_intermediate_files: Annotated[bool, typer.Option("--del-temp", "-dt", help="Delete intermediate GeoJSON & GPKG files")] = True,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose mode")] = False,
    record_time: Annotated[bool, typer.Option("--record-time", "-t", help="Record execution time")] = False,
):
    """
    Preprocess data on protected areas for each year of LULC data.
    Example usage: python main.py process-wdpa --config-dir ./config --force --skip-fetch --verbose --record-time
    
    Args:
        config_dir (str): Directory containing the configuration file.
        use_yearly_pa_raster (bool): Use less than or equal to PA year of establishment when TRUE, else use all years.
        auto_confirm (bool): Auto confirm all prompts.
        skip_fetch (bool): Skip fetching protected areas data from the API if the data already exists in the shared input directory.
        delete_intermediate_files (bool): Delete intermediate GPKG files
        verbose (bool): Verbose mode.
        record_time (bool): Record the execution time
    """
    if record_time:
        start_time = time.time()

    # TODO - to add flag (option) on skipping establishment year of protected areas
    config_path = os.path.join(config_dir, "config.yaml")
    check_file_exists(config_path)

    try:
        working_dir = os.getcwd()
        wp = WDPAWrapper(working_dir, config_path, verbose=verbose)
        
        # get the case study directory
        case_study_dir = str(wp.config.get("case_study_dir"))
        case_study = case_study_dir.split("/")[-1]

        # # STEP 1.0: Get the unique country codes from the LULC raster data
        country_codes = wp.get_lulc_country_codes() # returns {"GBR"} 

        # print to user to confirm country PAs to fetch
        print(f"Country protected areas to fetch: {country_codes}")

        # prompt the user to confirm the countries to fetch.
        if auto_confirm == False:
            confirm = typer.confirm("To confirm the processing of PA data for the above countries TYPE")
            if not confirm:
                err_console.print("Exiting...")
                raise typer.Exit(code=1)
        
        # # STEP 2.0: Fetch and process the protected areas for the selected countries
        print("Fetching protected areas for the selected countries...")
        # strip case study name from data/{case_study}
        merged_gpkg = case_study + "_merged_pa.gpkg"
        merged_gpkg = wp.protected_area_to_merged_geopackage(country_codes, merged_gpkg, skip_fetch)

        # # STEP 3.0: Rasterize the merged GeoPackage file
        print("Rasterizing the merged GeoPackage file...")
        lulc_dir = wp.config.get("lulc_dir")
        wp.rasterize_protected_areas(merged_gpkg, lulc_dir, use_yearly_pa_raster)

        if delete_intermediate_files:
            os.remove(merged_gpkg)
            typer.secho(f"{merged_gpkg} file has been deleted", fg=typer.colors.YELLOW)
        
        # # STEP 4.0: Raster calculation
        print("Summing LULC and PA rasters...")
        wp.sum_lulc_pa_rasters(
            input_path=os.path.join(working_dir, case_study_dir, "input"),
            output_path=os.path.join(working_dir, case_study_dir, "output"),
            lulc_dir=wp.config.get("lulc_dir"),
            use_yearly_pa_rasters= use_yearly_pa_raster
        )

        # # STEP 5.0: Reclassify input raster with impedance values
        print("Reclassifying the raster with impedance values...")
        wp.reclassify_raster_with_impedance()

        # # STEP 6: Compute affinity
        print("Computing affinity")
        wp.compute_affinity(os.path.join(working_dir, case_study_dir, "output", "affinity"))

    except Exception as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)
    
    if record_time:
        finish_time = time.time()
        elapsed_time = finish_time - start_time
        typer.secho(f"Elapsed time: {elapsed_time:.4f} seconds", fg=typer.colors.BLUE, bg=typer.colors.WHITE)

@app.command("process-osm")
def process_osm(
    config_dir: Annotated[str, typer.Option(..., help="Directory with the configuration file")] = "./config",
    api_type: Annotated[str, typer.Option("--api", "-a", help="API to use for fetching OSM data. Choose from 'overpass' or 'ohsome)")] = "ohsome",
    skip_fetch: Annotated[bool, typer.Option("--skip-fetch", "-s", help="Skip fetching OSM data. Overwrites existing data if FALSE")] = False,
    delete_intermediate_files: Annotated[bool, typer.Option("--del-temp", "-dt", help="Delete intermediate GeoJSON & GPKG files")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose mode")] = False,
    record_time: Annotated[bool, typer.Option("--record-time", "-t", help="Record execution time")] = False
    ):
    """
    Check if config exists. Fetches and translates Open Street Map data.
    Example usage: python main.py process-osm --config-dir ./config --api ohsome --verbose --del-temp --record-time

    Args:
        config_dir (str): Directory containing the configuration file.
        api_type (str): API to use for fetching OSM data. Choose from 'overpass' or 'ohsome
        skip_fetch (bool): Skip fetching OSM data. Overwrites existing data if FALSE.
        delete_intermediate_files (bool): Delete intermediate GeoJSON & GPKG files.
        verbose (bool): Verbose mode.
        record_time (bool): Record the execution time.

    # TODO - once ohsome API is implemented, provide separate option --api so user can choose from Ohsome and Overpass (Ohsome is preferable)
    """

    if record_time:
        start_time = time.time()

    config_path = os.path.join(config_dir, "config.yaml")
    check_file_exists(config_path)
    try:
        working_dir = os.getcwd()
        osm = OSMWrapper(working_dir, config_path, api_type, verbose)

        # STEP 1: Fetch OSM data
        if not skip_fetch:
            if len(osm.years) > 1:
                #prompt user to confirm which years to fetch
                year = typer.prompt("Type 'all' to use all years, or enter the year to fetch OSM data from the following years: ", osm.years,type=str)
                if year != "all":
                    # replace the years list with the selected year
                    osm.years = [int(year)]

        # fetch OSM data for the selected years using the selected API
        osm.osm_to_geojson(osm.years, skip_fetch)

        # STEP 2: Convert OSM data to merged GeoPackage (creates intermediate GeoJSON files for each year)
        osm.osm_to_merged_gpkg(osm.years,osm.api_type)
       
        # STEP 3: Delete intermediate files
        if delete_intermediate_files:
            osm.delete_temp_files(delete_geojsons=True, delete_gpkg_files=True)

    except Exception as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)
    
    if record_time:
        finish_time = time.time()
        elapsed_time = finish_time - start_time
        typer.secho(f"Elapsed time: {elapsed_time:.4f} seconds", fg=typer.colors.BLUE, bg=typer.colors.WHITE)
 

@app.command("enrich-lulc")
def enrich_lulc(
    config_dir: Annotated[str, typer.Option(..., help="Directory with the configuration file")] = "./config",
    api_type: Annotated[str, typer.Option("--api", "-a", help="API to use for fetching OSM data. Choose from 'overpass' or 'ohsome)")] = None,
    threads: Annotated[int, typer.Option("--threads", "-t", help="Number of threads to use for processing")] = 4,
    cog_compress: Annotated[bool, typer.Option("--cog-compress", "-c", help="Compress the output GeoTIFF files using Cloud Optimized GeoTIFF (COG)")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose mode")] = False,
    save_osm_stressors: Annotated[bool, typer.Option("--save-osm-stressors", "-s", help="Save OSM stressors to file")] = False,
    record_time: Annotated[bool, typer.Option("--record-time", "-t", help="Record execution time")] = False
    ):
    """
    Check if config exists. Processes and merges fetched data into output LULC dataset.
    Example usage: python main.py enrich-lulc --config-dir ./config --api ohsome --threads 4 --cog-compress --save-osm-stressors --verbose --record-time

    Args:
        config_dir (str): Directory containing the configuration file.
        api_type (str): API to use for fetching OSM data. Choose from 'overpass' or 'ohsome' or leave blank if none were used.
        threads (int): Number of threads to use for processing (default is 4).
        verbose (bool): Verbose mode.
        save_osm_stressors (bool): Save OSM stressors to file.
        record_time (bool): Record the execution time.
    """
    # TODO - to delete intermediate files (buffered features) as if we don't delete it they can raise errors for following runs
    if record_time:
        start_time = time.time()

    config_path = os.path.join(config_dir, "config.yaml")
    check_file_exists(config_path)
    print(os.getcwd())
    try:
        lew = LULCEnrichmentWrapper(os.getcwd(),config_path,api_type,threads, verbose)

        # prompt user to use all years or a specific year
        if len(lew.years) > 1:
            year = typer.prompt("Type 'all' to use all years, or enter the year to use for the LULC enrichment from the following years: ", lew.years,type=str)
            if year != "all":
                # replace the years list with the selected year
                lew.years = [int(year)]

        for year in lew.years:
            # 1. prepare and merge LULC and OSM data
            lew.initialise_data_processors(year)
            # 1.2 buffer vector data
            lew.buffer_vector_roads_and_railways()
            # 2. rasterize vector data
            lew.merge_lulc_osm_data(year, save_osm_stressors, cog_compress)

    except Exception as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)
    
    if record_time:
        finish_time = time.time()
        elapsed_time = finish_time - start_time
        typer.secho(f"Elapsed time: {elapsed_time:.4f} seconds", fg=typer.colors.BLUE, bg=typer.colors.WHITE)

@app.command("recalc-impedance")
def recalc_impedance(
    config_dir: Annotated[str, typer.Option(..., help="Path to the configuration file")] = "./config",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose mode")] = False,
    del_stressors: Annotated[bool, typer.Option("--del-stressors", "-s", help="Delete OSM stressors")] = False,
    decline_type: Annotated[str, typer.Option("--decline-type", "-dt", help="Type of decline to use for impedance calculation. Use either 'exp_decline' OR 'prop_decline'")] = "exp_decline",
    lambda_decay: Annotated[int, typer.Option("--lambda-decay", "-ld", help="Lambda decay value for impedance calculation")] = 500,
    k_value: Annotated[int, typer.Option("--k-value", "-k", help="K-value for impedance calculation")] = 500,
    record_time: Annotated[bool, typer.Option("--record-time", "-t", help="Record execution time")] = True
    ):
    """
    Check if config exists. Recalculates landscape impedance data for follow-up commputations.
    Example usage: python main.py recalc-impedance --config-dir ./config --verbose --del-stressors

    Args:
        config_dir (str): The path to the configuration directory.
        verbose (bool): Verbose mode
        del_stressors (bool): Delete OSM stressors (intermediate GeoTIFF files).
        decline_type (str): Type of decline to use for impedance calculation. Use either exp_decline OR prop_decline.
        lambda_decay (int): Lambda decay value for impedance calculation (if decline type is exponential).
        k_value (int): K-value for impedance calculation (if decline type is proportional).
        record_time (bool): Record the execution time.
    """
    if record_time:
        start_time = time.time()

    stressor_yaml_path = os.path.join(config_dir,"stressors.yaml")
    if not os.path.exists(stressor_yaml_path):
        raise FileNotFoundError("The stressors.yaml file is not found. Please add the file to the config directory.")
    
    config_path = os.path.join(config_dir, "config.yaml")
    check_file_exists(config_path)
    
    iw = ImpedanceWrapper( 
        types = None,
        decline_type = decline_type,
        lambda_decay = lambda_decay,
        k_value = k_value,
        config_path= config_path,
        config_impedance_path= os.path.join(config_dir,"config_impedance.yaml"),
        verbose=verbose
    )

    # prompt user to use all years or a specific year
    if len(iw.years) > 1:
        year = typer.prompt("Type 'all' to use all years, or enter the year to use for the LULC enrichment from the following years: ", iw.years,type=str)
        if year != "all":
            # replace the years list with the selected year
            iw.years = [int(year)]

    for year in iw.years:
        # 1. Process the impedance configuration (initial setup + lulc & osm stressors)
        # e.g. impedance_stressors = {'primary': '/data/data/output/roads_primary_2018.tif'}
        impedance_stressors = iw.process_impedance_config(year)

    # 2. Prompt user to update the configuration file
    
    # print the impedance stressors to the user in a table
    print_table("Impedance stressors", impedance_stressors)

    message = typer.style(
    "Please check/update the configuration file for impedance dataset (config_impedance.yaml).\n"
    "To confirm your configuration of ecological parameters for these biodiversity stressors TYPE",
    fg=typer.colors.YELLOW
    )

    confirm = typer.confirm(message) 

    if not confirm:
        err_console.print("Exiting...")
        raise typer.Exit(code=1)

    # 2.1. validate impedance configuration
    err_msg = ""
    while err_msg != "exit":
        err_msg = iw.validate_impedance_config(impedance_stressors)
    
        if err_msg != "exit":
            #print warning message
            print(f"""[bold yellow]The following errors was found in the configuration file:[/bold yellow]\n[bold red]{err_msg}[/bold red]""")
            message = print("Please update your impedance configuration file then TYPE")

            confirm = typer.confirm(message) 

            if not confirm:
                err_console.print("Exiting...")
                raise typer.Exit(code=1)

    for year in iw.years:
        # 3.  Get the maximum value of the impedance raster dataset
        impedance_ds, impedance_max = iw.get_impedance_max_value(year)

        # 3.0 Calculate impedance
        max_result_tif = iw.calculate_impedance(impedance_stressors,impedance_ds,impedance_max)
        if verbose:
            typer.secho(f"max_result_tif saved to: {max_result_tif}", fg=typer.colors.GREEN)

    # delete temporary impedance stressors.yaml
    if del_stressors:
        os.remove(stressor_yaml_path)
        typer.secho("Temporary OSM stressor file has been deleted", fg=typer.colors.RED)
        
    if record_time:
        finish_time = time.time()
        elapsed_time = finish_time - start_time
        typer.secho(f"Elapsed time: {elapsed_time:.4f} seconds", fg=typer.colors.BLUE, bg=typer.colors.WHITE)


#Test command
@app.command("test")
def init(firstname: str, surname: str, formal: bool = False):
    """
    For testing only. Example usage:
    python main.py test name surname --formal 
    typer run main.py test name surname --formal
    """
    if formal:
        typer.secho(f"Hello Mr. {firstname} {surname}", fg=typer.colors.GREEN, bg=typer.colors.YELLOW)
    else:
        typer.echo(f"Hello {firstname} {surname}")
    # err_console.print("This is an error message")


if __name__ == "__main__":
    app()

# Debugging
# if __name__ == "__main__":
#     process_wdpa(config_dir="./config", 
#     use_yearly_pa_raster=True, 
#     auto_confirm=True, 
#     skip_fetch=True, 
#     delete_intermediate_files=True, 
#     verbose=True, 
#     record_time=True)