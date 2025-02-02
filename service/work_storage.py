from google.cloud import storage
from service.singleton import SingletonMeta

class Storage(metaclass=SingletonMeta):
    """
    Взаємодія з бакетом, тому що іноді файли потрібно зберігати у хмарному сховищі
    """
    def upload_to_blob(self,bucket_name, source_file_name, destination_blob_name):
        """Uploads a file to the bucket."""
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        destination_blob_name = destination_blob_name.replace(" ","_").replace(":","").replace("+","").replace("-","").replace("(","").replace(")","")
        blob = bucket.blob(destination_blob_name)

        blob.upload_from_filename(source_file_name)
        # blob.make_public()
        print(f"File {source_file_name} uploaded to {destination_blob_name}.")
        return self.get_file_url(bucket_name,destination_blob_name)

    def delete_from_blob(self,bucket_name, destination_blob_name):
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)

        blob = bucket.blob(destination_blob_name)
        blob.delete()

    def get_file_url(self,bucket_name,file_name):
        return f"gs://{bucket_name}/{file_name}"

    def load_from_blob(self,bucket_name, nameAfterLoad, nameOnBucket):

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)

        blob = bucket.blob(nameOnBucket)
        
        blob.download_to_file(file_obj=nameAfterLoad)
    # Replace with your bucket name, source file path, and destination blob name
    # blob_rld = upload_blob('bucket_audio_euwest3', 'P2PNLINK1.wav', 'audio/P2PNLINK1.wav')

    # print(blob_rld)
