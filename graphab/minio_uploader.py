# minio_uploader.py MinIO Python SDK
from minio_client import MinioClient
from minio.error import S3Error, InvalidResponseError, ServerError
import os
import sys
import argparse
import time

print("Logs are redirected to /logs")
sys.stdout = open('logs/minio_uploader.log', 'w') #to log
sys.stderr = sys.stdout

class MinioWriter(MinioClient):
    def __init__(self):
        super().__init__()

    def put_file(self, input_dir:str, bucket_name:str, output_dir:str):
        """
        Uploads a file to a MinIO bucket.
        
        Args:
            input_dir (str): Path to the file to be uploaded.
            bucket_name (str): Name of the MinIO bucket.
            output_dir (str): Destination path in the bucket.

        Returns:
            None
        """

        # create bucket if doesn't exist
        found = self.client.bucket_exists(bucket_name)
        if not found:
            self.client.make_bucket(bucket_name)
            print("Created bucket", bucket_name)
        else:
            print("Bucket", bucket_name, "already exists")

        # upload the file, renaming it in the process
        self.client.fput_object(
            bucket_name, output_dir, input_dir,
        )

        config = self.client.get_bucket_versioning(bucket_name)
        print(f"Versioning: {config.status}")

        # NOTE - versioning doesn't recognise VersioningConfig
        '''
        # Check if versioning is disabled
        if config.status.lower() == 'off':
            print("Versioning disabled")
        
            # Enable versioning by setting it to 'Enabled'
            self.client.set_bucket_versioning(bucket_name, VersioningConfig(ENABLED))  
        
            # Fetch the updated versioning status
            updated_config = self.client.get_bucket_versioning(bucket_name)
            if updated_config.status.lower() == 'enabled':  # Check if the versioning was successfully enabled
                print(f"Versioning enabled: {updated_config.status}")
        else:
            print(f"Versioning enabled: {config.status}")
        '''

        print(f"Source uploaded as object: {input_dir}")
        print(f"Bucket name: {bucket_name}")    
        print(f"Destination: {output_dir}")

    def put_dir(self, bucket_name:str, input_dir:str, ignore_folders: list[str]):
        """
        Uploads a directory to a MinIO bucket.

        Args:
            bucket_name (str): Name of the MinIO bucket.
            input_dir (str): Path to the directory to be uploaded.
            ignore_folders (list(str)): names of directories to ignore when uploading

        Returns:
            None
        """
        #ensure the directory exists
        if not os.path.isdir(input_dir):
            print(f"Error: {input_dir} is not a valid directory.")
            return
        
        # create bucket if doesn't exist
        found = self.client.bucket_exists(bucket_name)
        if not found:
            self.client.make_bucket(bucket_name)
            print("Created bucket", bucket_name)
        else:
            print("Bucket", bucket_name, "already exists")
        print("-" * 40)  
        
        # walk through the directory
        for root, dirs, files in os.walk(input_dir):
            dirs[:] = [d for d in dirs if d not in ignore_folders] # modify list of folders in place to exclude ignored folders

            for file_name in files:
                loc_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(loc_path, input_dir)

                try:
                    # if we want to put the local files to the bucket, put the same path to the following functions
                    self.client.fput_object(bucket_name, loc_path, loc_path)
                    print(f"Uploaded {rel_path} to bucket {bucket_name}")
                except S3Error as exc:
                    print(f"Error uploading {rel_path}: {exc}")
                print("-" * 40) 

    @staticmethod
    def retry(func, *args, retry_wait=10, **kwargs):
        """Run a function and retry once if it fails."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"First attempt failed: {e}")
            print(f"Retrying in {retry_wait} seconds...")
            time.sleep(retry_wait)
        try:
            return func(*args, **kwargs)
        except Exception as retry_err:
            print(f"Retry failed. Skipping. Error: {retry_err}")
            return None

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Upload files or directories to MinIO.")
        parser.add_argument("--bucket_name", required=True, help="Name of the MinIO bucket.")
        parser.add_argument("--input_dir", required=True, help="Path to the directory to upload.")

        args = parser.parse_args()
        input_dir = args.input_dir
        bucket_name = args.bucket_name
        log_dir = "logs"

        minio_writer = MinioWriter()
        print(minio_writer.client)  # This will print the Minio client object if created successfully.
        
        '''
        input_dir = "data/cat_aggr_buf_390m_test"
        bucket_name="pilot.2.graphab"
        '''

        result = MinioWriter.retry(minio_writer.put_dir, bucket_name, input_dir, ignore_folders='bucket_ext')
        if result is not None:
            print(f"Completed case study: {input_dir.split('/')[-1]}")

        result = MinioWriter.retry(minio_writer.put_dir, bucket_name, log_dir, ignore_folders='bucket_ext')
        if result is not None:
            print(f"Exported logs: {log_dir.split('/')[-1]}")

        # TODO - to implement uploads of multiple folders

        # Example upload the file to the bucket
        # minio_writer.put_file(input_dir, bucket_name, output_dir)
        # print(f"Uploaded {input_dir} to bucket {bucket_name}")
    except S3Error as err:
        print(f"Error: {err}")
    except InvalidResponseError as err:
        print(f"Invalid response: {err}")
    except ServerError as err:
        print(f"Server error: {err}")
    except Exception as err:
        print(f"An unexpected error occurred: {err}")