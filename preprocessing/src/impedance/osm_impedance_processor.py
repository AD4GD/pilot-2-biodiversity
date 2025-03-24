import os
import copy
# local imports
from utils import load_yaml
from impedance.interfaces.impedance_config_handler import ImpedanceConfigurationHandler

class OSMImpedanceProcessor(ImpedanceConfigurationHandler):
    """
    The Osm_impedance_processor class processes the OSM vector dataset to extract stressors causing edge effect on habitats.
    It updates the impedance configuration file with the OSM stressors (raster files for each OSM feature and subtype are created in 3rd notebook)
    """
    def __init__(self, config_impedance:dict, config:dict, params_placeholder:dict, impedance_stressors:dict, year:int,
            current_dir:str,output_dir:str,osm_stressor_path:str = "config/stressors.yaml") -> None:
        """
        Initialize the Impedance class with the configuration file paths and other parameters.

        Args:

            config (dict): The configuration file.
            config_impedance (dict): The impedance configuration file.
            params_placeholder (dict): The dictionary template for the configuration YAML file (for each stressor).
            impedance_stressors (dict): The dictionary for stressors, mapping stressor raster path to YAML alias.
            year (int): The year for which the edge effect is calculated.
            current_dir (str): The parent directory
            output_dir (str): The output directory
            osm_stressor_path (str): The path to the OSM stressors YAML file (default is 'config/stressors.yaml')
        """
        super().__init__(config, config_impedance, params_placeholder, impedance_stressors, year, current_dir, output_dir)

        # additional directories
        self.vector_dir = os.path.join(self.config.get('case_study_dir'), self.config.get('vector_dir'))

        # load road/railway types from the configuration file from the 3rd notebook
        self.osm_stressor_path = osm_stressor_path

        # # get the maximum value from the impedance raster dataset
        # if impedance_tif is not None:
        #     impedance_ds = gdal.Open(impedance_tif) # open raster impedance dataset
        #     impedance_max = get_max_from_tif(impedance_ds) # call function from above
        #     print (f"Impedance raster GeoTIFF dataset used is {impedance_tif}") # debug
        #     print (f"Maximum value of impedance dataset: {impedance_max}") # debug
        #     # close the dataset
        #     impedance_ds = None
        # else:
        #     raise FileNotFoundError(f"Impedance raster GeoTIFF dataset '{impedance_tif}' is not found! Please check the configuration file.") # stop execution

    def update_impedance_config(self):
        """
        Sequentially calls the methods to update the impedance configuration file with stressors and default decay parameters.
        - Updates the impedance configuration file with OSM stressors and default decay parameters.
        - Updates the impedance stressors dictionary with the OSM stressors and their raster paths.

        Returns:
            tuple: Tuple containing two dictionaries:
                - Impedance_stressors (dict) The dictionary of stressors, mapping stressor raster path to YAML alias.
                - Impedance_configuration (dict): The updated configuration file mapping stressors to default decay parameters.
        """
        
        osm_stressors = load_yaml(self.osm_stressor_path)
        self.config_impedance = self.prepare_config_impendance_file(osm_stressors)
        # add the OSM stressors to the impedance configuration file
        for osm_stressor_feature,osm_feature_subtypes in osm_stressors.items():
            if osm_feature_subtypes is not None:
                for osm_feature_subtype in osm_feature_subtypes:
                    raster_path = os.path.normpath(os.path.join(self.output_dir,f'{osm_stressor_feature}_{osm_feature_subtype}_{self.year}.tif'))
                    self.impedance_stressors[osm_feature_subtype] = raster_path
            # if there are no subtypes, add the feature itself
            else:
                raster_path = os.path.normpath(os.path.join(self.output_dir,f'{osm_stressor_feature}_{self.year}.tif'))
                self.impedance_stressors[osm_stressor_feature] = raster_path

        return self.impedance_stressors, self.config_impedance
    
    def prepare_config_impendance_file(self, osm_stressors:dict):
        """
        Inserts the OSM stressors and subtypes (for example the 'road' OSM feature has a subtype 'motorway') into the impedance configuration file.
        
        - Example osm_stressor_dict:
        { 
            roads: ['trunk', 'motorway', 'primary', 'secondary', 'tertiary'] # road types to be extracted from OSM
            railways: ['rail', 'light_rail', 'subway'] # railway types to be extracted from OSM
        }

        Args:
            osm_stressor_dict (dict): dictionary of OSM stressors and their subtypes
        Returns:
            dict: updated configuration file with OSM stressors and subtypes
        """
        vector = self.config_impedance.get('vector', {}) # access the vector section in YAML
  
        for osm_stressor_feature, osm_stressor_feature_subtypes in osm_stressors.items(): 
            print(f"Processing {osm_stressor_feature}...")
            # 1. create or update the key for each osm_stressor_feature in 'vector'
            if osm_stressor_feature not in vector:
                vector[osm_stressor_feature] = {}  # initialize the osm_stressor_feature as an empty dictionary
                
                # define the 'types' key for each osm_stressor as an empty dictionary (will be updated later)
                vector[osm_stressor_feature]['types'] = None  # initialize 'types' with empty value

                # check if the subtypes variable is not empty (contains subtypes)
                if osm_stressor_feature_subtypes is not None:
                    # update the types in the vector for the current osm_stressor
                    vector[osm_stressor_feature]['types'] = True # Update types with True
                    # loop through each subtype in the dynamic variable
                    for stressor_subtype in osm_stressor_feature_subtypes:
                        # write params_placeholder to vector for each type
                        vector[osm_stressor_feature][stressor_subtype] = copy.deepcopy(self.params_placeholder)
                else:
                    # update the types in the vector for the current osm_stressor
                    vector[osm_stressor_feature]['types'] = None # update types with empty value
                    vector[osm_stressor_feature] = copy.deepcopy(self.params_placeholder)
                
        # update the 'vector' section back into the main config_impedance
        self.config_impedance['vector'] = vector

        return self.config_impedance

