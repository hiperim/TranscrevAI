import pytest
import os
import numpy as np
import sys
import soundfile as sf
import tempfile
from pathlib import Path
import shutil
import time
import stat
import subprocess
from ctypes import windll
import psutil
from unittest.mock import Mock, patch
from src.logging_setup import setup_app_logging
from src.file_manager import FileManager, ANDROID_ENABLED
from src.audio_processing import AudioRecorder

logger = setup_app_logging()

def mock_audio_record():
    class MockAudioRecord:
        def __init__(self, *args, **kwargs):
            pass
        def startRecording(self):
            pass
        def read(self, size):
            return bytes(size)
        def stop(self):
            pass
        def release(self):
            pass
    return MockAudioRecord

@pytest.fixture
def generate_test_audio():
    def _generate(duration=5.0, speakers=2, sample_rate=16000):
        samples = int(duration * sample_rate)
        data = np.zeros(samples, dtype=np.float32)
        for i in range(speakers):
            freq = 440 * (i + 1)
            t = np.linspace(0, duration, samples)
            data += 0.5 * np.sin(2 * np.pi * freq * t)
        data = data / np.max(np.abs(data))
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp:
            temp_file = temp.name
            sf.write(temp_file, data, sample_rate)
            logger.debug(f"Generated test audio: {temp_file}")
            return temp_file
        for attempt in range(10):
            try:
                with open(temp_file, "rb") as f:
                    f.read(1024)
                break
            except PermissionError:
                    time.sleep(0.5 * (attempt + 1))     
    return _generate

@pytest.fixture
def temp_path(tmp_path_factory):
    # Cross-platform compatible temporary directory fixture
    base_temp = tmp_path_factory.getbasetemp()
    test_temp = base_temp / "test_audio"
    # Remove existing directory first
    if test_temp.exists():
        if sys.platform == "win32":
            try:
                # Kill process w/ open handles on test directory
                for proc in psutil.process_iter(["pid", "name"]):
                    try:
                        if any(x in proc.name().lower() for x in ["ffmpeg", "ffprobe", "python"]):
                            # Check if process has handles on test directory
                            proc_files = proc.open_files()
                            if any(str(test_temp) in f.path for f in proc_files):
                                logger.info(f"Terminating process {proc.pid} holding test files")
                                proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                import win32security
                # Reset NTFS permissions on each test run
                secdec = win32security.SECURITY_DESCRIPTOR()
                secdec.SetSecurityDescriptorOwner(win32security.ConvertStringSidToSid("S-1-1-0"), False)
                win32security.SetNamedSecurityInfo(str(test_temp), win32security.SE_FILE_OBJECT, win32security.DACL_SECURITY_INFORMATION, None, None, None, None)
                # Wait for system handle release
                time.sleep(0.5)
            except ImportError:
                pass
        if FileManager.is_mobile() and ANDROID_ENABLED:
            from jnius import autoclass
            Context = autoclass("android.content.Context")
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            # Verify storage permissions
            if AudioRecorder.ContextCompat.checkSelfPermission(activity, AudioRecorder.Manifest.permission.WRITE_EXTERNAL_STORAGE) != AudioRecorder.PackageManager.PERMISSION_GRANTED:
                raise PermissionError("Android storage permission not granted")
        # Cross-platform forced removal
        shutil.rmtree(test_temp, ignore_errors=True)
    test_temp.mkdir(exist_ok=True)
    yield test_temp
    # Cleanup after yield
    if sys.platform == "win32":
        # Give processes time to finish operations
        time.sleep(0.5)
        # Terminate any processes still holding files
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc_files = proc.open_files()
                if any(str(test_temp) in f.path for f in proc_files):
                    logger.debug(f"Test cleanup: Terminating process {proc.pid}")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    # Unified cleanup using python std. library
    def on_rm_error(func, path, exc_info):
        # Make read-only files writable and retry
        os.chmod(path, stat.S_IWRITE)
        try:
            func(path)
        except:
            # If still can't remove, skip instead of failing
            logger.debug(f"Couldn't remove {path}")
    for attempt in range(5):
        try:
            shutil.rmtree(test_temp, onerror=on_rm_error)
            break
        except Exception as e:
            logger.debug(f"Cleanup attempt {attempt+1} failed: {e}, waiting {wait_time}s")
            if sys == "win32":
                wait_time = 0.5
            if FileManager.is_mobile() and ANDROID_ENABLED:
                wait_time = 2
            time.sleep(wait_time)
    test_temp.mkdir(exist_ok=True)

@pytest.fixture
def mock_paths(monkeypatch):
    # mock android package name
    monkeypatch.setattr('config.app_config.APP_PACKAGE_NAME', 'com.transcrevai.app')
    # mock SharedStorage for android
    mock_storage = Mock()
    mock_storage.return_value.get_cache_dir.return_value = "C:\\mock\\android\\path" if sys.platform == "win32" else "/mock/android/path"
    monkeypatch.setattr('src.file_manager.SharedStorage', mock_storage)
    # mock windows paths
    if sys.platform == 'win32':
        monkeypatch.setattr('pathlib.Path.home', lambda: Path("C:/FakeUser"))

@pytest.fixture(scope="function")
def mock_android(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("ANDROID_ARGUMENT", "1")
    with patch("src.file_manager.FileManager.is_mobile", return_value=True), \
         patch("src.file_manager.ANDROID_ENABLED", True), \
         patch("jnius.autoclass") as mock_autoclass:
            android_classes = {"androidx.core.content.ContextCompat": Mock(checkSelfPermission=Mock(return_value=0)),
                               "android.content.pm.PackageManager": Mock(PERMISSION_GRANTED=0, PERMISSION_DENIED=1),
                               "android.Manifest$permission": Mock(RECORD_AUDIO="android.permission.RECORD_AUDIO", WRITE_EXTERNAL_STORAGE="android.permission.WRITE_EXTERNAL_STORAGE"),
                               "org.kivy.android.PythonActivity": Mock(mActivity=Mock()),
                               "android.media.MediaRecorder": Mock(AudioSource=Mock(MIC=1), OutputFormat=Mock(MPEG_4=2), AudioEncoder=Mock(AAC=3))}
            # Return appropriate mock based on requested class
            def get_android_class(cls_name):
                return android_classes.get(cls_name, Mock())
            mock_autoclass.side_effect = get_android_class
            yield

def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "timeout: mark test to timeout")
    config.option.asyncio_mode = "strict"