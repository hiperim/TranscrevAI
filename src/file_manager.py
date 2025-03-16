import os
import logging
import zipfile
import requests
import hashlib
import asyncio
import time
import tempfile
import platform # ?Replace it, as it's used only once?
import sys
import shutil   
from pathlib import Path
from typing import Union
from src.logging_setup import setup_app_logging
from config.app_config import APP_PACKAGE_NAME

ANDROID_ENABLED = False
try:
    if sys.platform == 'linux' and 'ANDROID_ARGUMENT' in os.environ:
        from androidstorage4kivy import SharedStorage
        from jnius import autoclass
        ANDROID_ENABLED = True
except ImportError:
    pass

logger = setup_app_logging()

def sanitize_path(user_input, base_dir):  
    resolved_path = Path(base_dir).joinpath(user_input).resolve()  
    if not resolved_path.is_relative_to(Path(base_dir).resolve()):  
        raise SecurityError("Attempted directory traversal")  
    return str(resolved_path)  

class SecurityError(RuntimeError):
    def __init__(self, message):
        logger.error(f"Security violation: {message}")
        super().__init__(message)

class PermissionManager:
    # Permission request codes
    AUDIO_PERMISSION_CODE = 1001
    STORAGE_PERMISSION_CODE = 1002

    @staticmethod
    def check_permission(permission):
        if not FileManager.is_mobile() or not ANDROID_ENABLED:
            return True  # Check not needed
        # Android enviroment
        try:
            from jnius import autoclass
            Activity = autoclass("org.kivy.android.PythonActivity")
            current_activity = Activity.mActivity
            ContextCompat = autoclass("androidx.core.content.ContextCompat")
            PackageManager = autoclass("android.content.pm.PackageManager")
            return ContextCompat.checkSelfPermission(current_activity, permission) == PackageManager.PERMISSION_GRANTED
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return False
    
    @staticmethod
    def request_permission(permission, request_code):
        if not FileManager.is_mobile() or not ANDROID_ENABLED:
            return True # Request not needed
        # Android enviroment
        try:
            from jnius import autoclass
            Activity = autoclass("org.kivy.android.PythonActivity")
            current_activity = Activity.mActivity
            ActivityCompat = autoclass("androidx.core.app.ActivityCompat")
            # Create java string array with 1 element
            String = autoclass("java.lang.String")
            permissions_array = String[1]()
            permissions_array[0] = permission
            # Request permission
            ActivityCompat.requestPermissions(current_activity, permissions_array, request_code)
            logger.info(f"Requested permission: {permission}")
            return True
        except Exception as e:
            logger.error(f"Error requesting permission: {e}")
            return False
    
    @staticmethod
    async def check_permission_result(request_code, timeout=5):
        if not FileManager.is_mobile() or not ANDROID_ENABLED:
            return True # Check not needed
        # Android enviroment
        try:
            from jnius import autoclass
            import time
            Context = autoclass("android.content.Context")
            Activity = autoclass("org.kivy.android.PythonActivity")
            PackageManager = autoclass("android.content.pm.PackageManager")
            current_activity = Activity.mActivity
            preferences = current_activity.getSharedPreferences("TranscrevAIPermissions", Context.MODE_PRIVATE)
            # Get initial timestamp
            initial_ts = preferences.getLong("timestamp", 0)
            # Wait for permission response with timeout
            start_time = time.time()
            while time.time() - start_time < timeout:
                # Check if we have new results
                current_ts = preferences.getLong("timestamp", 0)
                stored_request_code = preferences.getInt("permission_request_code", -1)
                if current_ts > initial_ts and stored_request_code == request_code:
                    # There is a result match for request code
                    grant_results = preferences.getString("grant_results", "")
                    if grant_results:
                        # Convert to intergers and split with comma
                        grant_results = [int(r) for r in grant_results.split(",") if r]
                        if grant_results and grant_results[0] == PackageManager.PERMISSION_GRANTED:
                            logger.info(f"Permission granted for request: {request_code}")
                            return True
                        else:
                            logger.warning(f"Permission denied for request: {request_code}")
                            return False
                # Wait before checking again
                await asyncio.sleep(0.5)
            logger.warning(f"Permission request timed out: {request_code}")
            return False
        except Exception as e:
            logger.error(f"Error checking permission result: {e}")
            return False
    
    @staticmethod
    async def request_audio_permission():
        if not FileManager.is_mobile() or not ANDROID_ENABLED:
            return True # Request not needed
        try: # Android enviroment
            from jnius import autoclass
            Manifest = autoclass("android.Manifest$permission")
            # Check if already granted
            if PermissionManager.check_permission(Manifest.RECORD_AUDIO):
                return True
            # Request permission
            if PermissionManager.request_permission(
                    Manifest.RECORD_AUDIO, PermissionManager.AUDIO_PERMISSION_CODE):
                # Wait for result
                return await PermissionManager.check_permission_result(PermissionManager.AUDIO_PERMISSION_CODE)
            return False
        except Exception as e:
            logger.error(f"Error requesting audio permission: {e}")
            return False
    
    @staticmethod
    async def request_storage_permission():
        if not FileManager.is_mobile() or not ANDROID_ENABLED:
            return True # Request not needed
        try: # Android enviroment
            from jnius import autoclass
            Manifest = autoclass("android.Manifest$permission")
            # Check for storage permission
            if PermissionManager.check_permission(Manifest.WRITE_EXTERNAL_STORAGE) and PermissionManager.check_permission(Manifest.READ_EXTERNAL_STORAGE):
                return True
            # Request write permission (implies read on older android versions)
            if PermissionManager.request_permission(Manifest.WRITE_EXTERNAL_STORAGE, PermissionManager.STORAGE_PERMISSION_CODE):
                # Wait for result
                return await PermissionManager.check_permission_result(PermissionManager.STORAGE_PERMISSION_CODE)
            return False
        except Exception as e:
            logger.error(f"Error requesting storage permission: {e}")
            return False

class FileManager():
    def is_mobile():
        return sys.platform != 'win32' and hasattr(sys, 'getandroidapilevel')

    @staticmethod
    def get_base_directory(subdir=""):
        from pathlib import Path
        base = Path(__file__).resolve().parent.parent
        return str(base / subdir) if subdir else str(base)
        
    @staticmethod
    def get_data_path(subdir="") -> str:
        if FileManager.is_mobile() and ANDROID_ENABLED:
            try:
                # Request storage permissions for android 6.0+
                FileManager.request_storage_permission()
                shared_storage = SharedStorage() # type: ignore
                base = Path(shared_storage.get_cache_dir()) / "app_data"
            except Exception as e:
                logger.warning(f"Android storage error: {e}, using fallback path")
                base = Path(f"/data/data/{APP_PACKAGE_NAME}/files") # Android storage
        else:
            base = Path(__file__).parent.parent / "data"
        full_path = base / subdir
        return full_path.as_posix()
    
    @staticmethod
    async def get_data_path_async(subdir="") -> str:
        # Async version for requests with runtime permission
        if FileManager.is_mobile() and ANDROID_ENABLED:
            try:
                # Request storage permissions
                from src.file_manager import PermissionManager
                permission_granted = await PermissionManager.request_storage_permissions()
                if permission_granted:
                    shared_storage = SharedStorage() # type: ignore
                    base = Path(shared_storage.get_cache_dir()) / "app_data"
                else:
                    logger.warning("Storage permission denied, using internal storage")
                    base = Path(f"/data/data/{APP_PACKAGE_NAME}/files")
            except Exception as e:
                logger.warning(f"Android storage error: {e}, using fallback path")
                base = Path(f"/data/data/{APP_PACKAGE_NAME}/files")
        else:
            base = Path(__file__).parent.parent / "data"
        full_path = base / subdir
        os.makedirs(str(full_path), exist_ok=True)
        return full_path.as_posix()

    @staticmethod
    def get_unified_temp_dir() -> str:
        base_temp = FileManager.get_data_path("temp")
        FileManager.ensure_directory_exists(base_temp)
        temp_dir = tempfile.mkdtemp(dir=base_temp, prefix=f"temp_{os.getpid()}_",suffix=f"_{int(time.time())}")
        FileManager._set_temp_permissions(temp_dir)
        return FileManager.validate_path(temp_dir)

    @staticmethod
    def ensure_directory_exists(path):
        try:
            os.makedirs(path, exist_ok=True)
            if "temp" in path and os.name != 'nt':
                os.chmod(path, 0o777)
        except Exception as e:
            logger.error(f"Directory creation failed: {path}")
            raise RuntimeError(f"Filesystem error: {str(e)}")
        
    @staticmethod
    def _set_temp_permissions(path: str) -> None:
        try:
            if platform.system() in ["Linux", "Darwin"]:
                os.chmod(path, 0o700)
                logger.debug(f"Set permissions on temp directory: {path}")
        except Exception as e:
            logger.warning(f"Temp permission setting failed: {str(e)}")
            # Do not crash - log error and continue
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Failed path: {path}", exc_info=True)
    
    @staticmethod
    def request_storage_permission():
        # Request storage permission on android 6.0+
        if not FileManager.is_mobile() or not ANDROID_ENABLED:
            return True  # Not Android, so permissions not needed
        try:
            from jnius import autoclass
            Activity = autoclass("org.kivy.android.PythonActivity")
            current_activity = Activity.mActivity
            ContextCompat = autoclass("androidx.core.content.ContextCompat")
            PackageManager = autoclass("android.content.pm.PackageManager")
            Manifest = autoclass("android.Manifest$permission")
            ActivityCompat = autoclass("androidx.core.app.ActivityCompat")
            Build = autoclass("android.os.Build")
            # Read and write for complete storage access
            read_permission = Manifest.READ_EXTERNAL_STORAGE
            write_permission = Manifest.WRITE_EXTERNAL_STORAGE
            # Check if permissions are already granted
            read_granted = ContextCompat.checkSelfPermission(current_activity, read_permission) == PackageManager.PERMISSION_GRANTED
            write_granted = ContextCompat.checkSelfPermission(current_activity, write_permission) == PackageManager.PERMISSION_GRANTED
            # For Android 6.0+, request permissions if not granted
            if (not read_granted or not write_granted) and Build.VERSION.SDK_INT >= 23:
                logger.info("Requesting storage permissions from user")
                # Build list of permissions to request
                permissions_to_request = []
                if not read_granted:
                    permissions_to_request.append(read_permission)
                if not write_granted:
                    permissions_to_request.append(write_permission)
                if permissions_to_request:
                    # Convert list to java string array
                    String = autoclass("java.lang.String")
                    permissions_array = String[len(permissions_to_request)]()
                    for i, permission in enumerate(permissions_to_request):
                        permissions_array[i] = permission
                    # Request permissions
                    REQUEST_STORAGE_PERMISSION = 2  # Request code
                    ActivityCompat.requestPermissions(current_activity, permissions_array, REQUEST_STORAGE_PERMISSION)
                    # Inform the user about the request
                    Toast = autoclass("android.widget.Toast")
                    toast_message = "Storage permissions are required"
                    toast = Toast.makeText(current_activity, toast_message, Toast.LENGTH_LONG)
                    toast.show()
                    # Return current status (app will need to handle retries)
                    logger.info("Storage permission request dialog shown to user")
            return read_granted and write_granted
        except Exception as e:
            logger.error(f"Error requesting storage permissions: {e}")
            return False

    @staticmethod
    def validate_path(user_path: str) -> str:
        try:
            resolved = Path(user_path).resolve(strict=False)
            # Define platform-specific allowed directories
            allowed_dirs = []
            if FileManager.is_mobile() and ANDROID_ENABLED:
                try:
                    allowed_dirs.append(Path(SharedStorage().get_cache_dir())) # type: ignore
                    allowed_dirs.append(Path(f"/data/data/{APP_PACKAGE_NAME}/files")) # Android storage
                except Exception:
                    pass
            # Desktop paths
            base_dir = Path(__file__).parent.parent / "data"
            allowed_dirs.append(base_dir)
            # Temporary directory is also allowed
            import tempfile
            allowed_dirs.append(Path(tempfile.gettempdir()))
            # Require at least one valid allowed directory
            if not allowed_dirs:
                raise SecurityError("No valid directories configured")
            # Check that path is under an allowed directory
            if not any(resolved.is_relative_to(d) for d in allowed_dirs if d.exists()):
                logger.error(f"Path validation failed: {resolved} not in allowed directories")
                raise SecurityError(f"Path violation: {resolved}")
            return str(resolved)
        except ValueError as e:
            logger.error(f"Path validation failed: {e}")
            raise SecurityError("Invalid path") from e

    @staticmethod
    def save_audio(data, filename="output.wav") -> str:
        try:
            safe_dir = FileManager.validate_path("inputs")
            output_path = os.path.join(safe_dir, filename)
            FileManager.ensure_directory_exists(os.path.dirname(output_path))
            with open(output_path, 'wb') as f:
                f.write(data)
            logger.info(f"Audio file saved: {output_path}")
            return output_path
        except OSError as ose:
            logger.error(f"File system error: {ose.strerror}")
            raise 
        
    @staticmethod
    def save_transcript(data: Union[str, list], filename="output.txt") -> None:
        try:
            output_path = os.path.join(FileManager.get_data_path("transcripts"), filename)
            FileManager.ensure_directory_exists(os.path.dirname(output_path))
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(str(data))
            logger.info(f"Transcript saved: {output_path}")
        except Exception as e:
            logger.error(f"Transcript save failed: {e}")
            raise

    @staticmethod
    def _sync_download_and_extract(url, language_code, output_dir):
        model_path = os.path.join(output_dir, language_code)
        if os.path.exists(model_path) and any(os.listdir(model_path)):
            logger.info(f"Existing model found: {language_code}")
            return model_path
        zip_path = os.path.join(output_dir, f"{language_code}.zip")
        for attempt in range(3):
            try:
                logger.info(f"Downloading model: {language_code}")
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        f.write(chunk)
                # Create a temporary directory for extraction
                temp_extract_dir = os.path.join(output_dir, f"temp_{language_code}")
                if os.path.exists(temp_extract_dir):
                    shutil.rmtree(temp_extract_dir)
                os.makedirs(temp_extract_dir, exist_ok=True)
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(temp_extract_dir)
                # Checks if there is only one file and if folder is empty
                contents = os.listdir(temp_extract_dir)
                if len(contents) == 1 and os.path.isdir(os.path.join(temp_extract_dir, contents[0])):
                    nested_dir = os.path.join(temp_extract_dir, contents[0])
                    # Create the final model directory
                    if os.path.exists(model_path):
                        shutil.rmtree(model_path)
                    os.makedirs(model_path, exist_ok=True)
                    # Only copy the required folders
                    required_folders = ["am", "conf", "graph", "ivector"]
                    for folder in required_folders:
                        src_folder = os.path.join(nested_dir, folder)
                        dst_folder = os.path.join(model_path, folder)
                        if os.path.exists(src_folder):
                            shutil.copytree(src_folder, dst_folder)
                else:
                    # No nested directory: directly copy required folders
                    if os.path.exists(model_path):
                        shutil.rmtree(model_path)
                    os.makedirs(model_path, exist_ok=True)
                    required_folders = ["am", "conf", "graph", "ivector"]
                    for folder in required_folders:
                        src_folder = os.path.join(temp_extract_dir, folder)
                        dst_folder = os.path.join(model_path, folder)
                        if os.path.exists(src_folder):
                            shutil.copytree(src_folder, dst_folder)
                    # Clean up
                if os.path.exists(temp_extract_dir):
                    shutil.rmtree(temp_extract_dir)
                os.remove(zip_path)
                logger.info(f"Model extracted: {model_path}")
                # Verify required files exist
                required_files = ["am/final.mdl", "conf/model.conf", "graph/phones/word_boundary.int", "graph/Gr.fst", "graph/HCLr.fst", "ivector/final.ie"]
                missing = [f for f in required_files if not os.path.exists(os.path.join(model_path, f))]
                if missing:
                    logger.warning(f"Some model files missing after extraction: {missing}")
                return model_path
            except Exception as e:
                logger.error(f"Model download failed on attempt {attempt + 1}: {e}")
                time.sleep(2 * (attempt + 1)) 
        if os.path.exists(zip_path):
            os.remove(zip_path)
            raise RuntimeError(f"Failed to download and extract model")

    @staticmethod
    async def download_and_extract_model(url, language_code, output_dir):
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if not parsed.scheme.startswith('http'):
            raise ValueError("Invalid model URL")
        with requests.Session() as session:
            session.mount(url, requests.adapters.HTTPAdapter(max_retries=3))
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, FileManager._sync_download_and_extract, url, language_code, output_dir)
    
    @staticmethod 
    def cleanup_temp_dirs():
        base_temp = FileManager.get_data_path("temp")
        for temp_dir in os.listdir(base_temp):
            dir_path = os.path.join(base_temp, temp_dir)
            try:
                if os.path.isdir(dir_path):
                    shutil.rmtree(dir_path)
            except Exception as e:
                logger.warning(f"Temp cleanup failed: {dir_path}")