from minio import Minio
from urllib3.exceptions import MaxRetryError, LocationParseError, NameResolutionError
from urllib3 import PoolManager, Retry
from dotenv import load_dotenv
import os

load_dotenv()  # take environment variables

class MinioClient:
    def __init__(self):
        self.access_key = os.getenv("MINIO_ACCESS_KEY")
        self.secret_key = os.getenv("MINIO_SECRET_KEY")
        self.api_url = "minio-ad4gd-api.dashboard-siba.store" #os.getenv("MINIO_API_URL")
        self.client = self.create_client()
        

    def create_client(self):
        #Create and CONNECTS a client with the MinIO server playground, its access key
        #and secret key.
        try:
            client = Minio(self.api_url,
                        access_key=self.access_key,
                        secret_key=self.secret_key,
                        http_client=PoolManager(
                                timeout=10,
                                retries=Retry(
                                        total=2,
                                        backoff_factor=0.2,
                                        status_forcelist=[500, 502, 503, 504]
                                )
                        )
            )
        except MaxRetryError as err:
                print("ERROR MAXRETRYERROR")

        except LocationParseError as err:
                print(err.message)

        except NameResolutionError as err:
                print(err.message)

        except LocationParseError as err:
                print(err.message)
                
        return client