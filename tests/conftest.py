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
                from ctypes import windll, wintypes
                import win32security
                # Reset permissions on each test run
                secdec = win32security.SECURITY_DESCRIPTOR()
                secdec.SetSecurityDescriptorOwner(win32security.ConvertStringSidToSid("S-1-1-0"), False)
                win32security.SetNamedSecurityInfo(str(test_temp), win32security.SE_FILE_OBJECT, win32security.DACL_SECURITY_INFORMATION, None, None, None, None)
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
    yield test_temp
    
    # Unified cleanup using python standard library
    def on_remove_error(func, path, exc_info):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    for _ in range(3):
        try:
            shutil.rmtree(test_temp, onerror=on_remove_error)
            break
        except Exception as e:
            if FileManager.is_mobile() and ANDROID_ENABLED:
                # for compatibility with android media scanner (might hold files briefly)
                time.sleep(2 ** _)
            else:
                time.sleep(0.5 * _)
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