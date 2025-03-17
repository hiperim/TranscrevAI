package com.transcrevai.app;

import org.kivy.android.PythonActivity;
import android.os.Bundle;
import android.util.Log;
import android.content.Context;
import android.content.SharedPreferences;
import androidx.annotation.NonNull;

public class PermissionActivity extends PythonActivity {
    private static final String TAG = "TranscrevAI";
    private static final String PERM_PREFS_NAME = "TranscrevAIPermissions";
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.d(TAG, "TranscrevAI PermissionActivity created");
    }
    
    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        
        // Store results in SharedPreferences so python can access them
        SharedPreferences prefs = getSharedPreferences(PERM_PREFS_NAME, Context.MODE_PRIVATE);
        SharedPreferences.Editor editor = prefs.edit();
        
        // Store request code
        editor.putInt("permission_request_code", requestCode);
        
        // Store permissions as string with comma as sep.
        StringBuilder permStr = new StringBuilder();
        for (String permission : permissions) {
            permStr.append(permission).append(",");
        }
        editor.putString("permissions", permStr.toString());
        
        // Store grant results as string with comma as sep.
        StringBuilder resultStr = new StringBuilder();
        for (int result : grantResults) {
            resultStr.append(result).append(",");
        }
        editor.putString("grant_results", resultStr.toString());
        
        // Timestamp to detect new results
        editor.putLong("timestamp", System.currentTimeMillis());
        
        editor.apply();
        Log.d(TAG, "Permission results stored: " + requestCode);
    }
}