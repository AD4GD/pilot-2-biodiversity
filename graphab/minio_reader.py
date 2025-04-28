import argparse
from minio.error import S3Error, InvalidResponseError, ServerError
from dotenv import load_dotenv
from minio_client import MinioClient
import os
import sys

print("Logs are redirected to /logs")
sys.stdout = open('logs/minio_reader.log', 'w') #to log
sys.stderr = sys.stdout

class MinioReader(MinioClient):
    def __init__(self):
        super().__init__()
        
    def read_buckets(self):
        """
        This method lists all buckets in the MinIO server.

        Returns:
            list: A list of buckets.
        """
        buckets = self.client.list_buckets()
        return buckets
    
    def read_bucket(self, bucket_name:str):
        """
        This method lists all objects in a specified bucket.

        Args:
            bucket_name (str): The name of the bucket to read from.

        Returns:
            list: A list of objects in the bucket.
        """
        try:
            objects = self.client.list_objects(bucket_name, recursive=True)
            return objects
        except S3Error as err:
            print(f"Error: {err}")
        except InvalidResponseError as err:
            print(f"Invalid response: {err}")
        except ServerError as err:
            print(f"Server error: {err}")
        except Exception as err:
            print(f"An unexpected error occurred: {err}")
     
    def save_object_locally(self, bucket_name:str, object_name:str, data_dir:str, skip_existing:bool=False, verbose:bool=True):
        """
        This method downloads an object from a specified bucket and saves it to a local directory.
        It creates the directory if it doesn't exist and skips downloading if the file already exists.

        Args:
            bucket_name (str): The name of the bucket to read from.
            object_name (str): The name of the object to save.
            data_dir (str): The local directory to save the object to.
            skip_existing (bool): Whether to skip downloading existing files.
            verbose (bool): Whether to print verbose output.

        Returns:
            str: The name of the object that was saved.
        """
        try:
            # extract internal path from the object name
            # previous version:
            # internal_path = os.path.join(data_dir,*object_name.split("/")[1:-1])
            internal_path = os.path.join(data_dir, object_name)
            file_name = object_name.split("/")[-1]
            # if the file already exists, skip downloading
            if skip_existing:
                    if os.path.exists(os.path.join(internal_path, file_name)):
                            return None
            # create the directory if it doesn't exist
            os.makedirs(internal_path, exist_ok=True)
            # download the object to the specified directory
            self.client.fget_object(bucket_name, object_name, internal_path + "/" + file_name)
            if verbose:
                print(f"Object {object_name} downloaded to {data_dir}")
        except Exception as err:
            print(f"An unexpected error occurred: {err}")
            return object_name

    def get_ICT_folders_from_bucket(self, bucket_name: str) -> list:
        """
        Retrieve and filter folders from the bucket that contain 'ICT' in their name.
        Args:
            bucket_name (str): The name of the bucket.
        Returns:
            list: A list of filtered folder paths containing 'ICT'.
        """
        bucket_objects = self.read_bucket(bucket_name)
        folders = set()  # filter out the folders containing 'ICT' in their path - use a set to avoid duplicates

        for obj in bucket_objects:
            object_name = obj.object_name
            # Get the prefix up to the last '/' — the folder part
            if '/' in object_name:
                folder_path = object_name.rsplit('/', 1)[0]  # e.g., "ict_data/subfolder"
                if 'ict' in folder_path.lower():
                    folders.add(folder_path + '/')  # normalize with trailing slash

        print(f"Folders with external data in bucket are: {folders}")
        return list(folders)  # convert set back to list
        
    def save_all_objects_from_bucket(self, bucket_name:str, skip_existing_files:bool=False, verbose:bool=False):
        """
        Save all objects from a bucket to a local directory.

        Args:
            bucket_name (str): The name of the bucket to read from.
            skip_existing_files (bool): Whether to skip downloading existing files.
            verbose (bool): Whether to print verbose output.
        
        Returns:
            list: A list of failed files (if any).
        """
        # Iterate through the objects in the bucket and print their names
        bucket_objects = self.read_bucket(bucket_name)
        objects = []
        failed_files = []
        for obj in bucket_objects:
            objects.append(obj.object_name)
            failed_files.append(self.save_object_locally(bucket_name,obj.object_name, "data", skip_existing_files, verbose))
        print(f"Objects to save from bucket are: {objects}")
        return failed_files

    def save_selected_folders_from_bucket(self, bucket_name: str, folders: list[str], skip_existing_files: bool = False, verbose: bool =True):
        """
        Save only selected folders from an EXTERNAL bucket to a local directory ('bucket_ext', hardcoded).

        Args:
            bucket_name (str): The name of the bucket to read from.
            folders (list of str): List of folder name prefixes to download.
            skip_existing_files (bool): Whether to skip downloading existing files.
            verbose (bool): Whether to print verbose output.

        Returns:
            list: A list of failed files (if any).
        """
        bucket_objects = self.read_bucket(bucket_name)
        objects = []
        failed_files = []
        local_dir = 'bucket_ext'

        for obj in bucket_objects:
            object_name = obj.object_name
            if any(object_name.startswith(folder.rstrip('/') + '/') for folder in folders): # filter by needed folders
                if verbose:
                    print(f"Downloading object: {object_name}")
                
                objects.append(object_name)
                failed_files.append(
                    self.save_object_locally(bucket_name, object_name, local_dir, skip_existing_files, verbose)
                )

        if verbose:
            print(f"Objects to save from external bucket are: {objects}")
        return failed_files

# testing
if __name__ == "__main__":
    # Example usage python minio-reader.py <bucket_name> -skip-existing-files -verbose
    parser = argparse.ArgumentParser(description="Minio Reader Script")
    parser.add_argument("--bucket_name", type=str, help="Name of the bucket to read from Graphab data")
    parser.add_argument("--ext_bucket_name", type=str, help="Name of the bucket to read from external data")
    parser.add_argument("--skip-existing-files", action="store_true", help="Skip downloading existing files")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    bucket_name = args.bucket_name
    ext_bucket_name = args.ext_bucket_name
    skip_existing_files = args.skip_existing_files
    verbose = args.verbose

    minio_reader = MinioReader()
    print(minio_reader.client)  # This will print the Minio client object if created successfully.
    # read all objects from the bucket
    failed_files = minio_reader.save_all_objects_from_bucket(bucket_name, skip_existing_files, verbose)
    # print failed files
    for file in failed_files:
        if file is not None:
            print("Failed to download", file)

    # read all objects from external data (MiraMon)
    folders = minio_reader.get_ICT_folders_from_bucket(ext_bucket_name)
    failed_files_ext = minio_reader.save_selected_folders_from_bucket(ext_bucket_name, folders=folders, skip_existing_files=skip_existing_files, verbose=verbose)
    # print failed files
    for file in failed_files:
        if file is not None:
            print("Failed to download", file)