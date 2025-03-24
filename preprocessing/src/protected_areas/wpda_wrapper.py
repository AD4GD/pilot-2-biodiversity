# external imports
import os

# local imports
from protected_areas.wdpa_preprocessor import WDPAPreprocessor
from protected_areas.pa_processor_wrapper import PAProcessorWrapper
from protected_areas.pa_rasterizer import PARasterizer
from protected_areas.update_land_impedance import UpdateLandImpedance
from protected_areas.landscape_affinity_estimator import LandscapeAffinityEstimator
from protected_areas.lulc_pa_raster_sum import LulcPaRasterSum
from utils import load_yaml


class WDPAWrapper():
    """
    This class is a wrapper to abstract the preprocessing the input data for the ingesting protected areas data from WDPA API. \n
    It contains methods, which call a series of functions to that fetch and process the protected areas data, rasterize the protected areas, sum the LULC and PA rasters, reclassify the raster data with impedance values, and compute the affinity between the protected areas.
    """

    def __init__(self, working_dir:str,config_path:str, verbose:bool) -> None:
        """
        Initialize the WDPAWrapper class

        Args:
            working_dir (str): path to the current/working directory
            config_path (str): path to the configuration file
            verbose (bool): verbose output
        """

        self.working_dir = working_dir
        self.config = load_yaml(config_path)
        self.verbose = verbose

        #NOTE External data from API should always be stored in the shared directory
        self.pa_geojson_dir = os.path.abspath(os.path.join(working_dir, "data", "shared", "input", "protected_areas"))
        os.makedirs(self.pa_geojson_dir, exist_ok=True)
        # self.pa_input_dir = os.path.abspath(os.path.join(working_dir,self.config.get("case_study_dir"), self.config.get("input_dir"), "protected_areas"))
        # os.makedirs(self.pa_input_dir, exist_ok=True)
        self.pa_output_dir = os.path.abspath(os.path.join(working_dir, self.config.get("case_study_dir"), "output", "protected_areas"))
        os.makedirs(self.pa_output_dir, exist_ok=True)
        self.pa_output_data_dir = os.path.join(self.pa_output_dir, "pa_data")
        os.makedirs(self.pa_output_data_dir, exist_ok=True)

    def get_lulc_country_codes(self) -> dict:
        """
        Fetch the country codes for the LULC rasters

        Returns:
            dict: A dictionary of unique ISO3 country codes.
        """
        # initialize the WDPAPreprocessor class
        lulc_ccp = WDPAPreprocessor(self.config, self.working_dir, self.verbose)
        # fetch the unique country codes from input LULC raster data
        lulc_country_codes = set().union(*dict(lulc_ccp.fetch_lulc_country_codes(self.pa_output_dir)).values())
        return lulc_country_codes
    
    def protected_area_to_merged_geopackage(self, lulc_country_codes:dict, output_file:str, skip_fetch:bool=False) -> str:
        """
        For each unique country code, fetch and process the protected areas and merge them into a single GeoPackage file.
        API used fetches most up to date protected areas.

        Args:
            lulc_country_codes (dict): A dictionary of unique country codes.
            output_file (str): The name of the output GeoPackage file.
            skip_fetch (bool): A boolean value to skip fetching the PAs for countries that have an existing GeoJSON file.
        
        Returns:
            str: The path to the merged GeoPackage file.
        """
      
        self.pa_geojson_dir
        os.makedirs(self.pa_geojson_dir, exist_ok=True)
        # list to store the names of the GeoJSON files
        geojson_filepaths = []

        # initialize the PA_Processor_Wrapper class
        Pa_processor = PAProcessorWrapper(
            lulc_country_codes, 
            self.config['api_url'],
            self.config['token'],
            self.config['marine'],
            self.pa_geojson_dir
        )
        # if skip_fetch:
        #     geojson_filepaths = [os.path.join(self.pa_geojson_dir, file) for file in os.listdir(self.pa_geojson_dir)]
        # else:
        Pa_processor.process_all_countries(skip_fetch)
        geojson_filepaths = Pa_processor.save_all_country_geoJSON()
        if not geojson_filepaths:
            geojson_filepaths = [os.path.join(self.pa_geojson_dir, file) for file in os.listdir(self.pa_geojson_dir)]

        # merge all the GeoJSON files into a single GeoPackage file
        gpkg = Pa_processor.merge_geojsons_to_geopackage(geojson_filepaths, output_file)
        # print(f"GeoPackage file created: {gpkg}")
        return gpkg
    
    def rasterize_protected_areas(self, merged_gpkg:str, lulc_dir:str, pa_to_yearly_rasters:bool) -> None:
        """
        Rasterize the protected areas by year of establishment.

        Args:
            merged_gpkg (str): The file name to the merged GeoPackage file.
            lulc_dir (str): The path to the directory containing the LULC raster data.
            pa_to_yearly_rasters (bool): Rasterize the protected areas by year of establishment
        Returns:
            None
        """
 
        raster_output_dir = os.path.join(self.pa_output_dir, "pa_rasters")
        os.makedirs(raster_output_dir, exist_ok=True)

        case_study = self.config['case_study_dir'].split('/')[-1]

        rp = PARasterizer(merged_gpkg, lulc_dir, case_study, raster_output_dir)
        rp.reproject_pa_data(rp.lulc_metadata.crs_info["epsg"],filter_by_year=pa_to_yearly_rasters)
        rp.rasterize_pa_geopackage(rp.lulc_metadata, pa_to_yearly_rasters, keep_intermediate_gpkg=False)

    def sum_lulc_pa_rasters(self,input_path:str, output_path:str, lulc_dir:str, use_yearly_pa_rasters:bool) -> None:
        """
        Sum the LULC and PA raster data.

        Args:
            input_path (str): The path to the input directory.
            output_path (str): The path to the output directory.
            lulc_dir (str): The path to the directory containing the LULC raster data.
            use_yearly_pa_rasters (bool): Use yearly PA rasters
        Returns:
            None
        """
        lprs = LulcPaRasterSum(input_path,output_path,lulc_dir,use_yearly_pa_rasters,lulc_with_null_path="lulc_temp", pa_path="pa_rasters", lulc_upd_compr_path="lulc_pa")
        lprs.assign_no_data_values()
        lprs.combine_pa_lulc()

    def compute_affinity(self, affinity_dir:str='affinity') -> None:
        """
        Compute the affinity between the protected areas.

        Args:
            affinity_dir (str): The path to the directory where the affinity data will be saved.

        Returns:
            None
        """
        os.makedirs(affinity_dir, exist_ok=True)

        if self.config["subcase_study"]:
            impedance_dir = os.path.join(self.working_dir, self.config["case_study_dir"], self.config['impedance_dir'].split('/')[0], self.config["subcase_study"] + "_" + self.config['impedance_dir'].split('/')[-1])
        else:
            impedance_dir = os.path.join(self.working_dir, self.config["case_study_dir"], self.config['impedance_dir'])
        
        lae = LandscapeAffinityEstimator(impedance_dir, affinity_dir)
        lae.compute_affinity(os.listdir(impedance_dir))


    def reclassify_raster_with_impedance(self) -> None:
        """
        Reclassify the raster data with impedance values.
        
        Returns:
            None
        """
        uli = UpdateLandImpedance(self.config, self.working_dir)
        uli.update_impedance()


# Example usage
if __name__ == "__main__":
    working_dir = os.getcwd()
    config_path = os.path.join(working_dir, "config", "config.yaml")    
    wp = WDPAWrapper(working_dir,config_path, verbose=True)
    # get the case study directory
    case_study_dir = str(wp.config.get("case_study_dir"))
    case_study = case_study_dir.split("/")[-1]
    print(f"Case study: {case_study}")
    # country_codes = wp.get_lulc_country_codes()
    country_codes = {'FRA', 'ESP'}
    print(f"Country protected areas to fetch: {country_codes}")
    merged_gpkg = case_study + "_merged_pa.gpkg"
    merged_gpkg = wp.protected_area_to_merged_geopackage(country_codes, merged_gpkg, skip_fetch=True)
    lulc_dir = wp.config.get("lulc_dir")
    wp.rasterize_protected_areas(merged_gpkg, lulc_dir, pa_to_yearly_rasters=False)

    # delete the merged GeoPackage file
    os.remove(merged_gpkg)

    wp.sum_lulc_pa_rasters(
        input_path=os.path.join(working_dir, case_study_dir, "input"),
        output_path=os.path.join(working_dir, case_study_dir, "output"),
        lulc_dir=lulc_dir
    )
    wp.reclassify_raster_with_impedance()
    wp.compute_affinity(os.path.join(working_dir, case_study_dir, "output", "affinity"))

