import os
import subprocess
import warnings

# local imports
from vector_proc import VectorTransform
from utils import extract_layer_names

class VectorDataPreprocessor():
    """
    Preprocesses OSM vector data for rasterization, which includes reprojecting, fixing geometries 
    and buffering features in biodiversity stressor layers (roads and railways).
    """
    def __init__(self, config: dict, current_dir:str, vector_dir:str, year:int, lulc_crs:int, lulc_is_cartesian:bool) -> None:
        """
        Initializes the vector data preprocessor. Extracts vector layer names and checks if the CRS of the vector data matches the LULC data.

        Args:
            config (dict): configuration file
            current_dir (str): current directory
            vector_dir (str): vector directory
            year (int): year of the data
            lulc_crs (int): LULC CRS
            lulc_is_cartesian (bool): whether the LULC data is in cartesian coordinates
        """
        self.config = config
        self.year = year
        self.lulc_crs = lulc_crs
        self.lulc_is_cartesian = lulc_is_cartesian
        self.current_dir = current_dir
        self.vector_dir = vector_dir
        self.vector_refine = self.load_auxillary_data(self.current_dir, self.vector_dir , year)
        print(f"Path to the input vector dataset: {self.vector_refine}")
        self.vector_layer_names = self.check_vector_data_crs(self.vector_refine, self.lulc_crs)
        # specify the output directory
        self.vector_railways_buffered = os.path.join(self.current_dir,self.vector_dir , f"railways_{self.year}_buffered.gpkg")
        self.vector_roads_buffered = os.path.join(self.current_dir,self.vector_dir , f"roads_{self.year}_buffered.gpkg")
    
    def load_auxillary_data(self,current_dir:str, vector_dir:str, year:int) -> str:
        """
        Loads the auxiliary data (OSM or user-specified vector data) from the configuration file.

        Args:
            current_dir (str): current directory
            vector_dir (str): vector directory
            year (int): year of the data

        Returns:
            str: filename of the auxiliary data
        """
        # specify input vector data
        osm_data_template = self.config.get('osm_data', None)
        vector_filename = None # define a new variable which will be equal either osm_data or user_vector (depending on the configuration file)
        if osm_data_template is not None:
            osm_data = osm_data_template.format(year=year)
            user_vector = None
            vector_filename = osm_data 
            print ("Input raster dataset will be enriched with OSM data.")
        else:
            warnings.warn("OSM data not found in the configuration file.") 
            user_vector_template = str(self.config.get('user_vector',None))
            if user_vector_template is not None:
                user_vector = user_vector_template.format(year=year)
                vector_filename = user_vector
                print ("Input raster dataset will be enriched with user-specified data.")
            else:
                raise ValueError("No valid input vector data found. Neither OSM data nor user specified data found in the configuration file.")
            
        # print the name of chosen vector file
        print(f"Using vector file to refine raster data: {vector_filename}")
        return os.path.normpath(os.path.join(current_dir,vector_dir,vector_filename))
    

    def check_vector_data_crs(self, vector_filepath:str, crs:int) -> list:
        """
        Checks if the CRS of the vector data matches the input (LULC) data. If not, reprojects the vector data.

        Args:
            vector_refine (str): input vector file
            crs (int): CRS of the LULC data

        Returns:
            list: list of vector layer names
        """
        vector_layer_names = extract_layer_names(vector_filepath) 
        print(f"Layers found in the input vector file: {vector_layer_names}")
        formatted_layers = ', '.join(vector_layer_names)  # join layer names with a comma and space for readability
        print(f"Please continue if the layers in the vector file listed below are correct:\n {formatted_layers}.")

        # define full path with vector input directory
        # split path on last occurence of '/' and take the first part
        filepath = os.sep.join(vector_filepath.split(os.sep)[:-1])
        vector_data_dir = os.path.join(filepath)

        # check if crs matches input raster (lulc). If not, reproject the vector data
        Vt = VectorTransform(vector_data_dir)
        files_to_validate = Vt.reproject_vector(crs, overwrite=True)
        if len(files_to_validate) > 0:
            Vt.fix_geometry_layers_in_gpkg(Vt.geom_valid(files_to_validate), overwrite=True)
        return vector_layer_names
    
    def check_vector_geometry_validity(self, files_to_validate:list) -> bool:
        """
        Checks if the input vector layer is valid.

        Args:
            files_to_validate (list): The list of files to validate
        Returns:
            bool: True if the layer is valid, False otherwise
        """

        vector_data_dir = os.sep.join(str(files_to_validate[0]).split(os.sep)[:-1])
        vt = VectorTransform(vector_data_dir)
        invalid_files = vt.geom_valid(files_to_validate)
        vt.fix_geometry_layers_in_gpkg(invalid_files, overwrite=True)

      
    
    def buffer_features(self, layer:str, output_filepath:str, epsg:int=27700):
        """
        Buffer the features in the input vector layer based either on config file or 'width' column.
        If the instance is not in cartesian coordinates, a temporary transformation is used to apply the buffer in meters and then transform back to the original CRS.
        
        Args:
            layer (str): layer name
            output_filepath (str): output file path
            epsg (int, optional): EPSG code. Defaults to 27700.
        
        Returns:
            None
        """
        if os.path.exists(output_filepath):
            os.remove(output_filepath)

        # bring custom values of buffer width from the configuration file
        self.width_lev1 = self.config.get('width_lev1')
        self.width_lev2 = self.config.get('width_lev2')
        self.width_other = self.config.get('width_other')

        # check if the "width" column exists
        check_column_query = f"""
            SELECT COUNT(*) 
            FROM pragma_table_info('{layer}')
            WHERE name = 'width';
        """
        ogr_check_command = [
            'ogrinfo',
            self.vector_refine,
            '-dialect', 'SQLite',
            '-sql', check_column_query
        ]

        #TODO refactor this process 06/03/2025
        try:
            result = subprocess.run(ogr_check_command, check=True, capture_output=True, text=True)
            # extract the COUNT(*) value from the output
            column_exists = False
            for line in result.stdout.splitlines():
                 if "COUNT(*)" in line and "=" in line:  # Ensure the line contains COUNT(*) and an equals sign
                    count_value = int(line.split('=')[-1].strip())  # extract the number after '='
                    column_exists = count_value > 0  # set to true if count is greater than 0
                    break

        except Exception as e:
            column_exists = False
            return
            
        # build an SQL query to apply buffer based on "width" column and parameters from the config file
        if column_exists:
            print("Width column exists in subset.")
            subquery = f"""
                CASE 
                    WHEN "width" IS NULL 
                    OR CAST("width" AS REAL) IS NULL 
                    OR CAST("width" AS REAL) > {self.width_lev1} THEN 
                        CASE 
                            WHEN highway IN ('motorway', 'motorway_link', 'trunk', 'trunk_link') THEN {self.width_lev1}/2
                            WHEN highway IN ('primary', 'primary_link', 'secondary', 'secondary_link') THEN {self.width_lev2}/2
                            ELSE {self.width_other}/2 
                        END 
                    ELSE CAST("width" AS REAL)/2 
                END
            """
        else: # if 'width' is not specified
            print("Width column does not exist in subset. Using the custom value of width from the configuration file...")
            subquery = f"""{self.width_other}/2"""

        # DEBUG: print(subquery)
            
        # if it is not in cartesian coordinates, transform the geometry to a temporary cartesian CRS for buffering and then back to the original CRS
        # print(self.lulc_is_cartesian)
        if self.lulc_is_cartesian == False:
            query = f"""
                ST_Transform(
                    ST_Buffer(
                        ST_Transform(geom, {epsg}),
                        {subquery}
                    ),
                    {self.lulc_crs}
                ) AS geometry,
                *
            """
        else:
            query = f""" ST_Buffer(geom, {subquery}) AS geometry, * """

        # DEBUG: print(query)

        print(f"Buffering {layer} layer...")
        #NOTE only for roads and railways for now
        ogr2ogr_command = [
            'ogr2ogr',
            '-f', 'GPKG',
            output_filepath, # output file path
            self.vector_refine, # input file path (should be before the SQL statement)
            '-dialect', 'SQLite',
            '-sql', f"""
                SELECT
                {query}
                FROM {layer}; /* to specify layer of input file */
            """,
            '-nln', layer, # define layer in the output file
            '-nlt', 'POLYGON' # ensure the output is a polygon
        ]

        # execute ogr2ogr command
        try:
            result = subprocess.run(ogr2ogr_command, check=True, capture_output=True, text=True)
            print(f"Successfully buffered {layer} layer and saved to {output_filepath}.")
            if result.stderr:
                print(f"Warnings or errors:\n{result.stderr}")
                os.remove(output_filepath)
        except subprocess.CalledProcessError as e:
            print(f"Error buffering layer: {e.stderr}")
            os.remove(output_filepath)
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            os.remove(output_filepath)

        print("-"*40)


# for debugging
if __name__ == "__main__":
    from raster_metadata import RasterMetadata
    import yaml

    config_path = "./config/config.yaml"
    with open(config_path , 'r') as file:
        config = yaml.safe_load(file)
    working_dir = os.getcwd()
    vector_dir = os.path.join(working_dir,config["case_study_dir"],config['vector_dir'])
    year = 2017
    lulc_filepath = './data/shared/input/lulc/lulc_albera_ext_concat_{year}.tif'.format(year=year)
    # cls.assertTrue(os.path.exists(lulc_filepath))
    raster_metadata = RasterMetadata.from_raster(lulc_filepath)
    vp = VectorDataPreprocessor(
        config, 
        working_dir, 
        vector_dir, 
        year, 
        raster_metadata.crs_info["epsg"], 
        raster_metadata.is_cartesian
    )
    vp.buffer_features('railways', vp.vector_railways_buffered, vp.lulc_crs)
    vp.buffer_features('roads', vp.vector_roads_buffered, vp.lulc_crs)