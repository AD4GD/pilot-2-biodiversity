from osgeo import ogr
import yaml
import os

def load_yaml(path:str) -> dict:
        """
        Load a yaml file from the given path to a dictionary

        Args:
            path (str): path to the yaml file

        Returns:
            dict: dictionary containing the yaml file content
        """
        with open(path , 'r') as file:
            return yaml.safe_load(file)
        
def save_yaml(data:dict, path:str) -> None:
    with open(path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)
        print("Updated YAML configuration saved to:", path)
    

def get_max_from_tif(ds) -> float:
    """
    Extracts the maximum value from a GDAL raster dataset using GDAL's internal functions.
    
    INPUT (arguments):
        impedance_ds (gdal.Dataset): GDAL dataset object representing the raster.
    
    OUTPUT (returns):
        float: The maximum value in the raster.
    """
    # Check if the dataset is valid
    if ds is None:
        raise ValueError("The dataset is invalid or couldn't be opened.")
    # get the first raster band (assuming a single-band raster)
    band = ds.GetRasterBand(1)
    if band is None:
        raise ValueError("The raster band could not be retrieved.")
    
    # get the statistics for the band: min, max, mean, std_dev
    stats = band.GetStatistics(True, True)  # (approx_ok=True, force=True)
    # the maximum value is the second item in the stats list
    max_value = stats[1]
    # clean up
    ds = None
    return max_value

def extract_layer_names(gpkg_path:str) -> list:
    # open and read geopackage
    vector_data = ogr.Open(gpkg_path, update=0)  # update=0 means read-only mode
    layer_count = vector_data.GetLayerCount() # get the number of layers
    layers = [] # initialise list with layer names

    # extract layer names
    for i in range(layer_count):
        layer = vector_data.GetLayerByIndex(i)
        layer_name = layer.GetName()
        layers.append(layer_name)
    
    return layers


def extract_attribute_values_from_gpkg(vector_gpkg:str, layer_name:str, attribute:str) -> list:
    """
    Extract all unique attribute values from a vector GeoPackage file.
    
    Args:
        vector_gpkg (str): path to the vector GeoPackage file
        attribute (str): attribute name to extract unique values from
        
    Returns:
    list: list of unique attribute values
    """

    # open the vector data source
    ds = ogr.Open(vector_gpkg)
    if ds is None:
        raise RuntimeError(f"Failed to open the vector file: {vector_gpkg}")

    # get the layer from the data source (use first if not specified)
    if layer_name is None:
        layer_name = ds.GetLayer(0).GetName()
        print(f"Layer name not specified. Using the first layer: {layer_name}")

    # use SQL query to get distinct values
    sql_query = f"SELECT DISTINCT {attribute} FROM '{layer_name}'"
    res = ds.ExecuteSQL(sql_query)

    # collect unique values and release
    unique_values = [feature.GetField(attribute) for feature in res]
    ds.ReleaseResultSet(res)
    ds = None

    return unique_values

def find_stressor_params(config_dict: dict, search_key: str):
    """
    Recursively search for the first occurrence of a key in a nested dictionary.
    """
    if isinstance(config_dict, dict):
        if search_key in config_dict:
            return config_dict[search_key]  # return first match
        
        # recursively search in nested dictionaries
        for value in config_dict.values():
            stressor_params = find_stressor_params(value, search_key)
            if stressor_params is not None:
                return stressor_params  # stop searching once match foun

    return None  # return None if not found


def get_lulc_template(config:dict, year:int) -> str:
    """
    Gets the LULC template from the configuration file and returns the path to the LULC raster dataset for the input year.

    Args:
        config (dict): The configuration dictionary.
        year (int): The year for which the LULC template is required.
    
    Returns:
        lulc (str): The relative (from the working directory) filepath to the LULC raster dataset for the input year.
    """
    
    lulc_template = config.get('lulc', None)
    if lulc_template is None:
        raise("LULC template is null or not found in the configuration file.")
    else:
        # NOTE: For now we are using the first year in the list of years
        return os.path.normpath(os.path.join(config['lulc_dir'], lulc_template.format(year=year)))
    
def read_years_from_config(config:dict) -> list[int]:
    """
    Reads the years from the configuration file and returns a list of integer years.
    
    Args:
        config (dict): The configuration dictionary.
    
    Returns:
        list[int]: A list of years.
    """
    years = config.get('year', None)
    if years is None:
        raise TypeError("Year variable is null or not found in the configuration file.")
    elif isinstance(years, int):
        # cast to list
        return [years]
    else:
        # cast to list
        return [int(year) for year in years]