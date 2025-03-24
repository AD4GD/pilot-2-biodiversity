import os
import json
from datetime import datetime

class PAProcessor:
    """
    This protected area (PA) processor class is used to convert the json responses from the Protected Planet API to a single GeoJSON file per country.
    """
    def __init__(self, country:str) -> None:
        """
        Initialize the PA_Processor class

        Args:
            country (str): The country name.
        """
        self.country = country
        self.feature_collection = {
            "type": "FeatureCollection",
            "features": []
        }

    def add_PA_to_feature_collection(self, protected_areas:list[dict], exclude_redundant_ids:bool=True) -> dict:
        """
        Adds protected areas from the API response to the feature collection of the class.

        Args:
            protected_areas (list): A list of protected areas dictionaries.
            exclude_redundant_ids (bool): Exclude redundant IDs from the properties (default is True).

        Returns:
            feature_collection: The feature collection with protected areas.
        """

        # Counter for geometry print statements
        print_count = 0
        max_prints = 10
        
        # loop over protected areas        
        for pa in protected_areas:

            # convert date string to datetime object
            date_str = pa['legal_status_updated_at']

            # filter out protected areas if no date of establishment year is recorded
            if date_str is None:
                continue
            # format to YYYY-MM-DD
            else:
                try:
                    date = datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    # handle cases where the date is in a different format
                    try:
                        date = datetime.strptime(date_str, '%d/%m/%Y')
                    except ValueError:
                        # handle cases where the date is in a different format
                        date = datetime.strptime(date_str, '%m/%d/%Y')
                    
                # format to YYYY-MM-DD
                date_str = date.strftime('%Y-%m-%d')
              
            # extract geometry
            geometry = pa.get('geojson', {}).get('geometry')

            # TODO change this dubgging to only check first page? and work on verbose flag
            # debugging, print the geometry data
            if geometry is None:
                print(f"Warning: No geometry found for protected area {pa.get('name')} with ID {pa.get('id')}")
            elif print_count < max_prints:
                print(f"Geometry found for protected area {pa.get('name')} with ID {pa.get('id')}")
                print_count += 1
            if print_count == max_prints:
                print("More than 10 geometries found for protected areas...")
                print_count += 1  # prevent repeated summary messages

            if exclude_redundant_ids:
                pa['designation'].pop('id', None)
                pa['designation']['jurisdiction'] = pa['designation']['jurisdiction']["name"]
                pa['iucn_category'] = pa['iucn_category']['name']
                pa['legal_status'] = pa['legal_status']['name']
               

            # create feature with geometry and properties
            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "id": pa['id'],
                    "name": pa['name'],
                    "original_name": pa['name'],
                    "wdpa_id": pa['id'],
                    "management_plan": pa['management_plan'],
                    "is_green_list": pa['is_green_list'],
                    "iucn_category": pa['iucn_category'],
                    "designation": pa['designation'],
                    "legal_status": pa['legal_status'],
                    "year": date_str,
                }
            }
            # append the feature to the feature collection
            self.feature_collection["features"].append(feature) 

        return self.feature_collection

    def save_to_file(self, file_path:str) -> str:
        """
        Saves a country feature collection to a single GeoJSON file.

        Args:
            file_path (str): The path to the file.

        Returns:
            geojson_filepath (str): The path to the saved GeoJSON file.
        """
        # define filename for GeoJSON file
        geojson_filepath = os.path.join(file_path, f"{self.country}_protected_areas.geojson")
        # convert GeoJSON data to a string
        geojson_string = json.dumps(self.feature_collection, indent=4) 
        # write GeoJSON string to a file
        with open(geojson_filepath, 'w') as f:
            f.write(geojson_string)
        
        return geojson_filepath