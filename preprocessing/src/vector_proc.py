import os
from osgeo import ogr
import warnings
from subprocess import Popen, PIPE
import shutil

class VectorTransform:
    def __init__(self, directory):
        self.directory = directory
        self.file_list = []
        for filename in os.listdir(self.directory):
            if filename.lower().endswith('.gpkg'):
                self.file_list.append(filename)
        print(f"Found {len(self.file_list)} GeoPackage files in the directory: {self.directory}.")


    def check_vector_crs(self, filename:str, crs:str):
        """
        This function checks if the CRS of the input vector dataset is projected (Cartesian).

        Parameters:
        - None
        """
        file_path = os.path.join(self.directory, filename)
        ds = ogr.Open(file_path)
        layer = ds.GetLayer(0)
        spatial_ref = layer.GetSpatialRef()
        vector_crs = spatial_ref.GetAttrValue("AUTHORITY", 1)  
        print(f"CRS of the vector dataset '{filename}' is EPSG:{vector_crs}.")
        if vector_crs != crs:
            warnings.warn(f"CRS of the vector dataset '{vector_crs}' does not match the specified CRS: {crs}.")
            return False
        else:
            print(f"Good news! CRS of the vector dataset '{filename}' matches the specified CRS: {crs}.")
            return True

    def reproject_vector(self, crs:str, overwrite:bool=False):
        """
        This function transforms the input vector dataset to the specified CRS if the CRS of the input vector dataset is different from the specified CRS.
        """
        files_to_validate = []
        for filename in self.file_list:
            file_path = os.path.join(self.directory, filename)
            print(f"Checking the {file_path}...")
            if self.check_vector_crs(filename, crs) == False:
                print("Transforming the vector dataset to the specified CRS.")
                file_path = os.path.join(self.directory, filename)
                output_file = f"{file_path}_transformed.gpkg"
                # use ogr2ogr to transform the vector dataset with subprocess and crs
                ogr_command = f"ogr2ogr -f GPKG -t_srs EPSG:{crs} {output_file} {file_path}"
                proc = Popen(ogr_command, shell=True, stdout=PIPE, stderr=PIPE)
                stdout, stderr = proc.communicate()
                if proc.returncode != 0:
                    raise RuntimeError(stderr)
                else:
                    if overwrite:
                        os.remove(file_path)
                        os.rename(output_file, file_path)
                    print(f"Vector dataset '{filename}' was transformed successfully and the original file was overwritten.")
                files_to_validate.append(file_path)
        
        return files_to_validate


    def geom_valid(self, file_list:list[str]):
        """
        Checks the validity of geometries in all Geopackage files within the specified directory.

        Returns:
        - None: Prints out the validity status of the geometries.
        """

        invalid_files = {}  # to store invalid filepaths
        for file_path in file_list:
            filename = os.path.basename(file_path)
            # open geopackage file
            data_source = ogr.Open(file_path)
            
            if data_source is None:
                print(f"Failed to open GeoPackage: {file_path}")
                continue

            # get the number of layers in Geopackage
            num_layers = data_source.GetLayerCount()
            # initialize counters for invalid geometries
            invalid_features = 0
            # initialize list to write down IDs of invalid geometries
            invalid_features_list = []
            # initialize flag for geometry validity
            any_invalid_geometry = False

            invalid_layers = {}  # to store invalid layers
            
            # iterate through each layer
            for i in range(num_layers):
                layer = data_source.GetLayerByIndex(i)
                layer_name = layer.GetName()
                # calculate the total number of features in the layer
                total_features = layer.GetFeatureCount()
                
                # iterate through each feature in the layer
                for feature in layer:
                    total_features += 1 # increment the number of total fearu
                    geometry = feature.GetGeometryRef()
                    
                    if geometry is None: # skip issue with 'Error: 'NoneType' object has no attribute 'IsValid'
                        print(f"Warning: Feature ID {feature.GetFID()} in layer '{layer_name}' has no geometry.")
                        continue
                    
                    if not geometry.IsValid():
                        invalid_features += 1
                        
                        any_invalid_geometry = True
                        invalid_features_list.append(feature.GetFID())
                        """print(f"Invalid geometry found in file '{filename}', layer '{layer_name}':")"""
                        # print(f"Feature ID: {feature.GetFID()}")
                        """print(f"Geometry: {geometry.ExportToWkt()}")""" # to print geometry - dropped, as provides massive text

                # output validity status
                if any_invalid_geometry:
                    # calculate share of invalid geometries
                    share_invalid = (invalid_features / total_features) * 100 # if invalid_features > 0:
                    # raise warning
                    warning_message = (
                        f"At least one geometry in GeoPackage '{filename}' (layer '{layer_name}') is invalid. It might bring extra omissions in the further processing.\n"
                        f"Share of invalid geometries in GeoPackage '{filename}', layer '{layer_name}': {share_invalid:.4f}%.\n"
                        f"IDs of invalid features are: {invalid_features_list}."
                    )
                    warnings.warn(warning_message)
                    print("-"*40)  # separator for readability

                    invalid_layers[layer_name] = True
                    invalid_files[file_path] = invalid_layers
                else:
                    print(f"Good news! All vector geometries in GeoPackage '{filename}' (layer '{layer_name}') are valid.")
                    print("-"*40)  # separator for readability

                # show the share of invalid geometries in each layer                                        
            # close Geopackage
            data_source = None

        return invalid_files
        

    def fix_geometry_layer(self, layer:any,layer_name:any):
        # iterate over all features in the layer
        feature_to_fix_count = 0
        fixed_feature_count = 0
        invalid_feature_count = 0

        for feature in layer:
            geometry = feature.GetGeometryRef()
            
            if geometry is None: # skip issue with 'Error: 'NoneType' object has no attribute 'IsValid'
                print(f"Warning: Feature ID {feature.GetFID()} in layer '{layer_name}' has no geometry.")
                continue
            
            if not geometry.IsValid():
                feature_to_fix_count += 1 # increment the number of features to be fixed
                # attempt to fix the geometry
                fixed_geometry = geometry.MakeValid()
                
                if geometry is None: # skip issue with 'Error: 'NoneType' object has no attribute 'IsValid'
                    print(f"Warning: Feature ID {feature.GetFID()} in layer '{layer_name}' has no geometry.")
                    continue
                

                if fixed_geometry.IsValid():
                    # replace the geometry with the fixed one
                    feature.SetGeometry(fixed_geometry)
                    layer.SetFeature(feature)  # save the updated feature back to the layer
                    print(f"Fixed invalid geometry in layer '{layer_name}', feature ID: {feature.GetFID()}")
                    fixed_feature_count += 1 # increment the number of fixed features
                else:
                    print(f"Could not fix geometry in layer '{layer_name}', feature ID: {feature.GetFID()}")
                    invalid_feature_count += 1 # increment the number of features that cannot be fixed

        # estin 
        if feature_to_fix_count == 0:
            print (f"All geometries of features in the layer '{layer_name}' of the output vector are valid.")
            print("-" * 40)
            return True
        else:
            print(f"Layer '{layer_name}: {fixed_feature_count} geometries fixed.")
            if invalid_feature_count > 0:
                print(f"Layer '{layer_name}': {invalid_feature_count} geometries could not be fixed.")
                print("-" * 40)
                return False
            return True
        
    def fix_geometry_layers_in_gpkg(self, invalid_files:dict[str,dict[str,bool]], overwrite:bool=False):
        if len(invalid_files) == 0:
            return
        else:
            for file_path, layers in invalid_files.items():
                # open geopackage file
                data_source = ogr.Open(file_path)
            
                if data_source is None:
                    print(f"Failed to open GeoPackage: {file_path}")
                    continue

                # if fixed_gpkg is not specified, overwrite the file_path
                if overwrite is False:
                    fixed_gpkg = file_path
                else:
                    fixed_gpkg = file_path.replace(".gpkg", f"_fixed.gpkg")
                    shutil.copyfile(file_path, fixed_gpkg) # to copy file to a new one

                # open the output GeoPackage for editing
                data_source = ogr.Open(fixed_gpkg, update=1)
                is_valid = False

                # if invalid layers are not specified, fix all layers
                if layers is None:
                    for i in range(data_source.GetLayerCount()):
                        layer = data_source.GetLayerByIndex(i)
                        layer_name = layer.GetName()
                        is_valid = self.fix_geometry_layer(layer, layer_name)
                        if is_valid == False:
                            raise Exception(f"{layer_name} still contains invalid geometries")
                else:
                    for layer_name, invalid in layers.items():
                        if not invalid:
                            continue
                        else:
                            layer = data_source.GetLayerByName(layer_name)
                            is_valid = self.fix_geometry_layer(layer, layer_name)
                        if is_valid == False:
                            raise Exception(f"{layer_name} still contains invalid geometries")

                # close the data source
                del data_source

                # remove the original GeoPackage if it should be overwritten
                if overwrite:
                    shutil.copyfile(fixed_gpkg, file_path)
                    print(f"Fixed geometries and saved to {file_path}.")
                    os.remove(fixed_gpkg)
                else:
                    print(f"Fixed geometries and saved to {fixed_gpkg}.")
# Example usage:
# vector_transform = VectorTransform(directory)
# vector_transform.geom_valid()
