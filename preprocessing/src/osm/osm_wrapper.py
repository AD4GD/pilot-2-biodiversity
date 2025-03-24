import os 
from osm.overpass_wrapper import OverpassWrapper
from osm.osm_geojson_to_gpkg import OSMGeojsonToGpkg
from osm.ohsome_wrapper import OhsomeWrapper
from utils import load_yaml, read_years_from_config
import shutil

class OSMWrapper():

    def __init__(self, working_dir:str, config_path:str, api_type:str, verbose:bool) -> None:
        """
        Initialize the WDPAWrapper class

        Args:
            working_dir (str): path to the current/working directory
            config_path (str): path to the configuration file
            verbose (bool): verbose output
        """

        self.working_dir = working_dir
        self.config = load_yaml(config_path)
        self.api_type = api_type

        self.years = read_years_from_config(self.config)
        self.case_study_dir = self.config['case_study_dir']
        self.case_study = self.case_study_dir.split('/')[-1]
        self.verbose = verbose
        self.osm_output_data_dir = os.path.abspath(os.path.join(working_dir, "data","shared","input","osm_data",self.case_study))
        os.makedirs(self.osm_output_data_dir, exist_ok=True)

        self.input_dir = os.path.abspath(os.path.join(working_dir, self.case_study_dir,"input"))
        self.lulc_dir = os.path.abspath(self.config['lulc_dir'])

        # vector_dir is where the final merged gpkg files will be stored
        self.vector_dir = os.path.abspath(os.path.join(self.input_dir, 'vector'))
        os.makedirs(self.vector_dir, exist_ok=True)
        self.gpkg_dir = os.path.join(self.osm_output_data_dir, 'gpkg_temp')
        os.makedirs(self.gpkg_dir, exist_ok=True)
        

    def osm_overpass_to_geojson(self, years:list, skip_fetch:bool):
        """
        Handles fetching OSM data for all the years in the configuration file and convert them to geojson files.

        Args:
            years (list): a list of years to process (From the OSMPreprocessor class)
            skip_fetch (bool): whether to skip fetching OSM data or not. If FALSE, it will OVERWRITE any existing JSON files.
        """
        ow = OverpassWrapper(self.config, self.osm_output_data_dir, self.verbose, years)
        for year in years:
            # build the queries for the year
            queries = ow.overpass_query_builder(year, bbox=ow.bbox)
            
            # fetch the OSM data for the year
            intermediate_jsons = [os.path.join(self.osm_output_data_dir, file) for file in os.listdir(self.osm_output_data_dir) if f'overpass_pre_{year}.json' in file]
            if skip_fetch == True and len(intermediate_jsons) <= 0:
                raise ValueError(f"No JSON files found for year {year}. Please re-run the command with skip_fetch=False.")
            elif skip_fetch == False:
                intermediate_jsons = ow.fetch_osm_data(queries=queries, year=year)
                if self.verbose:
                    [print(f"Created JSON file: {intermediate_json}, ") for intermediate_json in intermediate_jsons]
 
            # convert the intermediate JSON files to GeoJSON files
            ow.convert_to_geojson(queries=queries, year=year)
            # fix invalid geometries in the GeoJSON files
            if self.verbose:
                print(f"Verbose outputs enabled, so filtered geometries will be created as new *_filtered.geojson files")
            ow.filter_geometries(queries=queries,year=year, overwrite_original= not(self.verbose))

    def osm_ohsome_to_geojson(self, years:list, skip_fetch:bool):
        """
        Handles fetching OSM data for all the years in the configuration file and convert them to geojson files.

        Args:
            years (list): a list of years to process (From the OSMPreprocessor class)
            skip_fetch (bool): whether to skip fetching OSM data or not. If FALSE, it will OVERWRITE any existing JSON files.
        """
        ow = OhsomeWrapper(self.config, self.osm_output_data_dir, years, self.verbose)
        all_years = True if len(years) > 1 else False # if more than one year is provided, then fetch all years combined into one JSON file
        year = years[-1]
        intermediate_jsons = [os.path.join(self.osm_output_data_dir, file) for file in os.listdir(self.osm_output_data_dir) if f'ohsome_pre_{year}.json' in file]
        if self.verbose:
            print(f"Verbose outputs enabled, so filtered features will be created as new *_filtered.geojson files")
        if skip_fetch == True and len(intermediate_jsons) <= 0:
            raise ValueError(f"No JSON files found for year {year}. Please re-run the command with skip_fetch=False.")
        elif skip_fetch == True:
            ow.convert_to_geojson(intermediate_jsons, year)
        else:
            ow.fetch_osm_data(years, ow.ohsome_query_builder(all_years), timeout=600)

    def osm_to_geojson(self, years:list, skip_fetch:bool):
        if self.api_type == 'overpass':
            self.osm_overpass_to_geojson(years, skip_fetch)
        elif self.api_type == 'ohsome':
            self.osm_ohsome_to_geojson(years, skip_fetch)
        else:
            raise ValueError("Invalid API type. Please use either 'overpass' or 'ohsome'.")
     
    def osm_to_merged_gpkg(self, years:list, api_type:str):
        """
        Converts the OSM GeoJSON files to GeoPackage files and merges them into a single GeoPackage file.

        Args:
            years (list): a list of years to process (From the OSMPreprocessor class)
            api_type (str): the API to use for fetching OSM data (either 'overpass' or 'ohsome')

        Returns:
            None: Writes the GeoPackage files to the output directory
        
        """
        for year in years:
            ogtg = OSMGeojsonToGpkg(self.osm_output_data_dir,self.gpkg_dir,target_epsg=4326, year=year, api_type=api_type)
            # if verbose mode is used then use the filtered.geojson files
            file_ending = '_filtered.geojson' if self.verbose else 'geojson'

            # replace .geojson with .gpkg for each file
            ogtg.gpkg_files = [file for file in ogtg.convert_geojson_to_gpkg(file_ending)]
            output_file = os.path.join(self.gpkg_dir, f'osm_merged_{year}.gpkg') # year added from OSM_PreProcessor class 
            fixed_gpkg_path = os.path.join(self.gpkg_dir, f'osm_merged_{year}_fixed.gpkg')
            ogtg.merge_gpkg_files(output_file)
            gpkg_path = ogtg.fix_geometries_in_gpkg(output_file, fixed_gpkg_path)
            #Move file to vector_dir for next component
            shutil.move(gpkg_path, os.path.join(self.vector_dir, f'osm_merged_{year}.gpkg'))

    
    def delete_temp_files(self, delete_geojsons:bool, delete_gpkg_files:bool):
        """
        Delete all intermediate GeoJSON files to save disk space.
        
        Args:
            delete_geojsons (bool): whether to delete GeoJSON files
            delete_gpkg_files (bool): whether to delete GeoPackage files
        Returns:
            None: Deletes all intermediate GeoJSON files from osm data directory
        """
        # delete all Overpass GeoJSON files
        if delete_geojsons:
            for file in os.listdir(self.osm_output_data_dir):
                if file.endswith('.geojson'):
                    os.remove(os.path.join(self.osm_output_data_dir, file))
            print(f"Deleted all GeoJSON files from {self.osm_output_data_dir}")
        
        if delete_gpkg_files:
            for file in os.listdir(self.gpkg_dir):
                if file.endswith('.gpkg') and 'osm_merged' not in file:
                    os.remove(os.path.join(self.gpkg_dir, file))
            print(f"Deleted all GeoPackage files from {self.gpkg_dir}")


if __name__ == "__main__":
    osm = OSMWrapper(os.getcwd(), "./config/config.yaml",api_type="ohsome", verbose=True)
    osm.osm_to_geojson(osm.years, skip_fetch=True)
    osm.osm_to_merged_gpkg(osm.years, osm.api_type)
    osm.delete_temp_files(True, True)
    print("OSM data processing complete.")