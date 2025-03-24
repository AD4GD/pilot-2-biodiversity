import os
import requests
import ssl
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import json
import time
from rich import print as rprint
# local imports
from utils import get_lulc_template
from reprojection import RasterTransform


# custom TLS Adapter to enforce TLSv1.2
class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.options |= ssl.OP_NO_SSLv3 | ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1  # enforce TLSv1.2+
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=ctx
        )


class OhsomeWrapper:

    def __init__(self, config:dict, output_dir:str, years:list[int], verbose:bool):
        self.config = config
        self.output_dir = output_dir
        self.verbose = verbose
        self.years = years
        # create a dictionary of LULC files and corresponding years
        lulc_series = {get_lulc_template(self.config, year):year for year in self.years}

        # We can use the first raster to get the bounding box, as all rasters for each case study should have the same extent
        lulc = list(lulc_series.keys())[0]

        if self.verbose:
            print(f"OSM data is to be retrieved for {self.years} years.")
            print ("-" * 30)
            print(f"Bounding box for the OSM data is to be retrieved from the raster: {lulc}")

        self.bbox = RasterTransform(raster_path=lulc).bbox_to_WGS84(print_details=self.verbose)
        # convert the bounding box to a string
        self.bbox = f"{self.bbox[1]},{self.bbox[0]},{self.bbox[3]},{self.bbox[2]}"
        
        self.session = requests.Session()
        # self.session.mount('https://', TLSAdapter())


    def ohsome_query_param_builder(self,bbox:str,showMetadata:str,properties:str,timestamps:str,osm_filter:str) -> dict:
        """
        Builds the query parameters for the ohsome API.

        Args:
            bbox (str): The bounding box for the query.
            showMetadata (str): Whether to include metadata in the response.
            properties (str): The properties to include in the response.
            timestamps (str): The timestamps for the query.
            osm_filter (str): The OSM filter for the query.
        """
    
        params = {
            "bboxes": bbox,
            "showMetadata": showMetadata,
            "properties": properties,
            "time": timestamps, 
            "filter": osm_filter
        }
        return params

    def ohsome_query_builder(self, all_years:bool, properties:str = "metadata,tags", showMetadata:str="true") -> dict:
        """
        Builds the query for the ohsome API.

        Args:
            all_years (bool): Whether to include all years from config in the query.
            properties (str): The properties to include in the response.
            showMetadata (str): Whether to include metadata in the response.
        
        Returns:
            query_dict (dict): A dictionary of the queries for each OSM filter.
        """

        query_dict = {}
        timestamps = "{year}-12-31"
        if all_years:
            timestamps = ",".join(f"{year}-12-31" for year in self.years)
        #get config keys with prefix 'ohsome_'
        filters = [(key.split('_')[-1],key) for key in self.config.keys() if 'ohsome_' in key]
        for filter_name,config_key in filters:
            query_dict[filter_name] = self.ohsome_query_param_builder(self.bbox, showMetadata, properties, timestamps, self.config[config_key])

        return query_dict

    def convert_to_geojson(self, json_files:list[str], year:int):
        """
        Converts the JSON files to GeoJSON files (Only used if skip_fetch is False).

        Args:
            json_files (list): The list of JSON files to convert.
            year (int): The year to use in the output filename.
        """

        for json_file in json_files:
            # if json_file.endswith(".
            filter_name = json_file.split('/')[-1].split('_')[0]
            output_filename = os.path.join(self.output_dir , f"{filter_name}_ohsome_pre_{year}.geojson")
            # load the JSON file
            with open(json_file, 'r') as f:
                data = dict(json.load(f))
            # get the features
            features = data.get("features", [])
            # if verbose save intermediate geojson files separately
            if self.verbose:
                output_filename = output_filename.replace(".geojson", "_filtered.geojson")
            # save the filtered data
            self.save_filtered_data(features, filter_name, output_filename)
  
    def save_filtered_data(self , features:list[dict], filter_name:str, output_filename:str):
        """
        Saves the filtered data to a GeoJSON file.

        Args:
            features (list): the list of dictionary features to filter and save.
            filter_name (str): The name of the filter.
            output_filename (str): The name of the output file.
        """

        for feature in features:
            # drop @ metadata keys except @snapshotTimestamp
            feature["properties"] = {key: value for key, value in feature.get("properties", {}).items() if key == "@snapshotTimestamp" or not key.startswith("@")}
        
        # save to geojson file
        with open(output_filename, 'w') as json_file:
            geojson = {
                "type": "FeatureCollection",
                "name": filter_name, # name of the layer
                "features": features
            }
            json.dump(geojson, json_file, indent=4)
        print(f"GeoJSON has been saved to {output_filename}")

    def fetch_osm_data(self, years:list[int], queries:dict, timeout:int=600 , url:str = "https://api.ohsome.org/v1/elements/geometry"):
        """
        Fetches the OSM data using the ohsome API. Using verbose mode will save the raw JSON files and filtered GeoJSON files.

        Args:
            years (list): The years to fetch the data for.
            queries (dict): The queries to use for fetching the data.
            timeout (int): The timeout for the request.
            url (str): The URL for the request.
        """

        query_start = time.time()
        for filter_name, query_params in queries.items():
            year = years[-1] # get the last year in the list to be used as the filename
            if len(years) == 1:  # if only one year is used, replace the year in the query with the actual year
                query_params['time'] = str(query_params['time']).format(year=year)
            # NOTE Only data with the matching snapshot timestamps are returned. This can include data from previous years as long as the timestamp matches
            output_filename = os.path.join(self.output_dir, f"{filter_name}_ohsome_pre_{year}.geojson")
            # try make the request
            try:
                response = self.session.post(url, data=query_params, timeout=timeout)  # use 'data' instead of 'params'
                if response.status_code == 200:
                    response_data = response.json()
                    # count features
                    feature_count = len(response_data.get("features",[])) # how many values corresponds to "features" key
                    # get the features list
                    features = response_data.get("features", [])

                    # save to JSON file
                    with open(output_filename.replace(".geojson", ".json"), 'w') as json_file:
                        json.dump(response_data, json_file, indent=4)
                    print(f"JSON has been saved to {output_filename.replace(".geojson", ".json")}")

                    # if verbose save intermediate geojson files separately
                    if self.verbose:
                        output_filename = output_filename.replace(".geojson", "_filtered.geojson")
                    # save the filtered data
                    self.save_filtered_data(features, filter_name, output_filename)
                else:
                    raise requests.RequestException(f"Request failed with status code: {response.status_code}")
            except requests.RequestException as e:
                print(f"Request failed for params: {query_params}. Error: {e}")
            
            query_finish = time.time()
            query_time = query_finish - query_start
            rprint(f"[bold blue] Query time: {query_time} seconds [/bold blue]") 
            rprint(f"[green] Number of features retrieved: {feature_count} [/green]")


if __name__ == "__main__":
    from utils import read_years_from_config, load_yaml
    config = load_yaml("./config/config.yaml")
    case_study_dir = config['case_study_dir']
    case_study = case_study_dir.split('/')[-1]
    osm_output_data_dir = os.path.abspath(os.path.join(os.getcwd(), "data","shared","input","osm_data",case_study))
    years = read_years_from_config(config)
    ow = OhsomeWrapper(config, osm_output_data_dir, years, verbose=True)
    all_years = True if len(years) > 1 else False
    skip_fetch = True
    if skip_fetch == False:
        ow.fetch_osm_data(years, ow.ohsome_query_builder(all_years=all_years))
    else:
        year = years[-1]
        # read all json files with the year in the name
        intermediate_jsons = [os.path.join(osm_output_data_dir, file) for file in os.listdir(osm_output_data_dir) if f'ohsome_pre_{year}.json' in file]
        ow.convert_to_geojson(intermediate_jsons, year)