import os
import json
import requests

# local imports
from utils import read_years_from_config, get_lulc_template
from reprojection import RasterTransform

class WDPAPreprocessor():
    """
    This class is responsible for preprocessing the input data for the ingesting protected areas data from WDPA API.
    The input LULC raster bounding box is extracted and used to fetch the unique ISO 3166-1 alpha-3 country code from the ohsome API.
    Since the LULC rasters have the same extent, we only need to fetch the country codes for one raster.
    """

    def __init__(self, config:dict,  current_dir:str, verbose:bool) -> None:
        """
        Initialize the WDPAPreprocessor

        Args:
            config (dict): dictionary containing the configuration parameters
            current_dir (str): the current directory

        """
        self.current_dir = current_dir
        self.config = config
        self.verbose = verbose


        # read lulc_dir
        self.lulc_dir = self.config.get('lulc_dir', None)
        if self.lulc_dir is None:
            raise ValueError("LULC directory is null or not found in the configuration file.")

        # read year 
        self.years = read_years_from_config(self.config)

        # each case study should have the same extent for LULC rasters, so we only need one raster to fetch the country codes
        self.lulc = get_lulc_template(self.config, self.years[0])
        if not os.path.exists(self.lulc):
            raise FileNotFoundError(f"LULC raster for year {self.years[0]} not found at {self.lulc}")

    #NOTE Ohsome API is using openstreetmap data, which may not be the best source to fetch country codes from bounding box with. The GAUL dataset provided by FAO (UN) is a better source for this but it is not available through API.
    def get_country_code_from_bbox(self, bbox:str, output_path:str) -> set:
        """
        This function sends a request to the ohsome API to get the country code from a given bounding box

        Args:
            bbox (str): bounding box in the format 'x_min,y_min,x_max,y_max'. It should be 'lon_min','lat_min',lon_max','lat_max'
            output_path (str): path to save the geojson file

        Returns:
            set: set of unique country codes
        """
        url = 'https://api.ohsome.org/v1/elements/geometry'
        data = {"bboxes": {bbox}, "filter": "boundary=administrative and admin_level=2", "properties": 'tags'}
        response = requests.post(url, data=data)

        
        # check if the request was successful
        if response.status_code == 200:
            response_json = response.json()
            print("Request was successful")
            # extract unique country names, filtering out None values
            # create set to handle only unique names
            unique_country_names = {
                feature['properties'].get('ISO3166-1:alpha3') 
                for feature in response_json.get('features', []) # filter out none values
                if feature['properties'].get('ISO3166-1:alpha3')
            }
    
            # print unique country names
            print(f"Countries covered by the bounding box are (ISO-3 codes): \n{'\n'.join(unique_country_names)}")
            print("-" * 40)

            # save JSON response to GeoJSON
            if output_path is not None:
                with open(os.path.join(output_path,"countries.geojson"), 'w') as f:
                    json.dump(response_json, f, indent=4)
            return unique_country_names
        else:
            raise Exception(f"Error: {response.status_code}")

        # TODO - raise warning if no countries in the respnse but request is successful
        
    def fetch_lulc_country_codes(self, output_path:str) -> dict[set]:
        """
        1. Fetch the country codes for the LULC raster. 
        2. LULC rasters for each case study SHOULD have the same extent, thus we only need to fetch the country codes for one raster.

        Args:
            output_path (str): path to save the geojson file (optional)

        Returns:
            dict: dictionary containing the country codes for each LULC raster
        """
        lulc_country_codes = {}
        x_min, y_min, x_max, y_max = RasterTransform(self.lulc).bbox_to_WGS84(print_details=self.verbose)
        bbox = f"{y_min},{x_min},{y_max},{x_max}" # changed! Ohsome API requires: 'lon_min','lat_min',lon_max','lat_max'
        lulc_country_codes[self.lulc] = self.get_country_code_from_bbox(bbox, output_path)
        return lulc_country_codes