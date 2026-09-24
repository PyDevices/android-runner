// SPDX-License-Identifier: MIT
package org.pydevices.runner;

import android.app.Activity;
import android.app.ActivityManager;
import android.content.Intent;
import android.os.Bundle;
import android.os.Process;
import java.util.List;

/**
 * Starts the Runner again in a fresh process (p4a_app/session.py).
 *
 * Runs in its own process (":relaunch", added to the manifest by
 * scripts/p4a_hook.py) so it outlives the Runner's. The Runner starts it while
 * still on screen, which is what lets this Activity start the Runner in turn:
 * Android blocks Activity starts from an app that is not in the foreground.
 */
public class Relauncher extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        int pid = pidExtra(getIntent());
        if (pid > 0 && pid != Process.myPid()) {
            // Starting the Runner while its old process lives would only hand
            // the old, closing Activity a new intent. /proc/<pid> can't tell:
            // it is hidden from this process. Ask the ActivityManager instead.
            Process.killProcess(pid);
            ActivityManager am = (ActivityManager) getSystemService(ACTIVITY_SERVICE);
            for (int i = 0; i < 60 && isRunning(am, pid); i++) {
                try {
                    Thread.sleep(50);
                } catch (InterruptedException e) {
                    break;
                }
            }
        }
        Intent next = new Intent(Intent.ACTION_MAIN);
        next.setClassName(getPackageName(), "org.kivy.android.PythonActivity");
        next.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(next);
        finish();
        overridePendingTransition(0, 0);
        Runtime.getRuntime().exit(0);
    }

    private static boolean isRunning(ActivityManager am, int pid) {
        List<ActivityManager.RunningAppProcessInfo> procs = am.getRunningAppProcesses();
        if (procs == null) {
            return false;
        }
        for (ActivityManager.RunningAppProcessInfo info : procs) {
            if (info.pid == pid) {
                return true;
            }
        }
        return false;
    }

    /** The "pid" extra. pyjnius puts a Python str as char[], not String. */
    private static int pidExtra(Intent intent) {
        Bundle extras = intent.getExtras();
        Object value = extras == null ? null : extras.get("pid");
        String text = value instanceof char[] ? new String((char[]) value) : String.valueOf(value);
        try {
            return Integer.parseInt(text.trim());
        } catch (NumberFormatException e) {
            return 0;
        }
    }
}
