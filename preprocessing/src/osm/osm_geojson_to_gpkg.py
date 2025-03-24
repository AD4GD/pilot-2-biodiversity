import shutil
from osgeo import ogr
import os
import subprocess

class OSMGeojsonToGpkg():
    """
    A class to convert GeoJSON files to GeoPackage files and merge them into a single GeoPackage file.
    """

    def __init__(self, osm_data_dir:str, gpkg_dir:str, target_epsg:str, year: int, api_type:str):
        """
        Initialize the OsmGeojson_to_gpkg class with the input directory, output directory, and target EPSG code.

        Args:
            osm_data_dir (str): the input directory containing GeoJSON files
            gpkg_dir (str): the output directory to save the GeoPackage files
            target_epsg (str): the target EPSG code to reproject the GeoJSON files to
        """

        self.osm_data_dir = osm_data_dir
        # create output directory if it does not exist
        os.makedirs(gpkg_dir, exist_ok=True)
        self.gpkg_dir = gpkg_dir
        self.target_epsg = target_epsg
        self.year = year
        self.api_type = api_type
        # initialize the list of GeoPackage files. NOTE: This is set by external code.
        self.gpkg_files = []


    def convert_geojson_to_gpkg(self, file_ending:str) -> list:
        """
        Convert all GeoJSON files in the input directory to GeoPackage files with the target EPSG code.

        Args:
            file_ending (str): the file ending of the GeoJSON files (if using verbose and overpass then it is 'filtered.geojson')
            
        Returns:
            list: a list of geopackage files
        """

        # loop through all geojson files in directory
        gpkg_files = []
        for filename in os.listdir(self.osm_data_dir):
            if filename.endswith(file_ending) and self.api_type in filename:
                geojson_file = os.path.join(self.osm_data_dir, filename)
                # create the output GeoPackage file path
                geopackage_file = os.path.join(self.gpkg_dir, filename.replace(file_ending, '.gpkg'))

                # since ohsome has geojson files with all years, we need to create a new geopackage file for each year from the config
                if self.api_type == 'ohsome':
                    year_of_file = geopackage_file.split('_')[-1].split('.')[0]
                    geopackage_file = geopackage_file.replace(f'{year_of_file}.gpkg', f'{self.year}.gpkg') 
            
                try:
                    command = ['ogr2ogr', '-f', 'GPKG', '-t_srs', f'EPSG:{self.target_epsg}', geopackage_file, geojson_file]
                    # if ohsome is specified, extract data from the specified year and prior
                    if self.api_type == 'ohsome':
                        # since ohsome has merged geojson files, we need to filter by year
                        geopackage_file.replace('.gpkg', f'_{self.year}.gpkg') 
                        # we need to rename the geometry field when using ohsome data
                        sql_query = f"SELECT \"_ogr_geometry_\" as geom, * FROM {filename.split('_')[0]} WHERE \"@snapshotTimestamp\" = '{self.year}-12-31'"
                        command.extend(['-sql', sql_query])
                    
                    #run the ogr2ogr command to convert the GeoJSON file to a GeoPackage file using subprocess
                    result = subprocess.run(command, capture_output=True, text=True)

                    print(f"Converted and modified {filename} to GeoPackage: {geopackage_file}")

                    #check error code
                    if len(result.stderr) > 0:
                        print(f"Warnings or errors:\n{result.stderr}")

                    # append filenames with a list
                    gpkg_files.append(geopackage_file.split('/')[-1])

                except subprocess.CalledProcessError as e:
                    print(f"Error processing {filename}: {e}")
                except Exception as e:
                    print(f"Unexpected error with {filename}: {e}")

        # return the list of geopackage files
        return gpkg_files
    
    def merge_gpkg_files(self, output_file:str):
        """
        Merge all GeoPackage files into a single GeoPackage file 

        Args:
            output_file (str): the output GeoPackage file
        """
        
        # debug print the list of GeoPackage files
        # print(self.gpkg_files)

        # initialize the GeoPackage using the first GeoPackage file
        print(self.gpkg_files)
        first_gpkg_file = str(self.gpkg_files[0])
        layer_name = first_gpkg_file.split(f"_{self.api_type}")[0]
        first_gpkg_file = os.path.join(self.gpkg_dir, first_gpkg_file)

        subprocess.run(['ogr2ogr', '-f', 'GPKG', output_file, first_gpkg_file, # output and input files
                '-s_srs', f'EPSG:{self.target_epsg}',  # set source CRS
                '-t_srs', f'EPSG:{self.target_epsg}', # set target CRS
                '-nln', layer_name # specify name of the layer
                ], check=True, capture_output=True, text=True) # to show log
        print(f"Initialized merged GeoPackage with CRS EPSG:{self.target_epsg} from {layer_name}.")
        for gpkg_file in self.gpkg_files[1:]:  # skip the first file because it's already added
            layer_name = gpkg_file.split(f"_{self.api_type}")[0]
            gpkg_file = os.path.join(self.gpkg_dir, gpkg_file)
            # run appending separate geopackages to empty merged geopackage (update if layers were previously written)
            try:
                result = subprocess.run(['ogr2ogr', '-f', 'GPKG', output_file, '-s_srs', f'EPSG:{self.target_epsg}', # for input file
                                                '-t_srs', f'EPSG:{self.target_epsg}', # for output file
                                                '-nln', layer_name, '-update', '-append', gpkg_file],
                                                check=True, 
                                                capture_output=True, 
                                                text=True)
                print(f"Added layer {layer_name} from {gpkg_file} to {output_file}")
                if len(result.stderr) > 0:
                    print(f"Warnings or errors:\n{result.stderr}")

            except subprocess.CalledProcessError as e:
                print(f"Error adding {layer_name}: {e.stderr}")
            except Exception as e:
                print(f"Unexpected error with {layer_name}: {e}")

    def fix_geometries_in_gpkg(self, input_gpkg:str, fixed_gpkg_path:str=None) -> str:
        """
        Fix invalid geometries in a GeoPackage file and save the fixed geometries to a new GeoPackage file.
        If fixed_gpkg is not specified, the input GeoPackage file will be overwritten.

        Args:
            input_gpkg (str): the input GeoPackage file
            fixed_gpkg_path (str): the output path for the fixed GeoPackage file (default is None)
        Returns:
            str: the path to the fixed GeoPackage file
        """

        # if fixed_gpkg is not specified, overwrite the input_gpkg
        copy_gpkg = False
        if fixed_gpkg_path is None:
            fixed_gpkg_path = input_gpkg
        else:
            shutil.copyfile(input_gpkg, fixed_gpkg_path) # to copy file to a new one
            copy_gpkg = True

        # open the output GeoPackage for editing
        data_source = ogr.Open(fixed_gpkg_path, update=1)

        for i in range(data_source.GetLayerCount()):            
            layer = data_source.GetLayerByIndex(i)
            layer_name = layer.GetName()
            feature_to_fix_count = 0
            fixed_feature_count = 0
            invalid_feature_count = 0

            # iterate over all features in the layer
            for feature in layer:
                geometry = feature.GetGeometryRef()
                if not geometry.IsValid():
                    feature_to_fix_count += 1 # increment the number of features to be fixed
                    # attempt to fix the geometry
                    fixed_geometry = geometry.MakeValid()

                    if fixed_geometry.IsValid():
                        # replace the geometry with the fixed one
                        feature.SetGeometry(fixed_geometry)
                        layer.SetFeature(feature)  # save the updated feature back to the layer
                        print(f"Fixed invalid geometry in layer '{layer_name}', feature ID: {feature.GetFID()}")
                        fixed_feature_count += 1 # increment the number of fixed features
                    else:
                        print(f"Could not fix geometry in layer '{layer_name}', feature ID: {feature.GetFID()}")
                        invalid_feature_count += 1 # increment the number of features that cannot be fixed

        if feature_to_fix_count == 0:
            print (f"All geometries of features in the layer '{layer_name}' of the output vector are valid.")
            print("-" * 40)
        else:
            print(f"Layer '{layer_name}: {fixed_feature_count} geometries fixed.") 
            print(f"Layer '{layer_name}': {invalid_feature_count} geometries could not be fixed.")
            print("-" * 40)

        # close the data source
        del data_source

        # return the path to the fixed GeoPackage file
        if copy_gpkg == True:
            return fixed_gpkg_path
        else:
            return input_gpkg