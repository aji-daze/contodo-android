#!/usr/bin/env python3
"""ConTodo の Android プロジェクト一式を、この1ファイルから書き出す。
GitHub Actions が実行して APK を作る。"""
import base64
import os
import urllib.request

ROOT = os.getcwd()
PKG_DIR = "app/src/main/java/app/contodo"
RES = "app/src/main/res"


def w(path, content):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


# ---------------------------------------------------------------- gradle
w("settings.gradle", r"""pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "ConTodo"
include ':app'
""")

w("build.gradle", r"""plugins {
    id 'com.android.application' version '8.7.3' apply false
}
""")

w("gradle.properties", r"""org.gradle.jvmargs=-Xmx3g -Dfile.encoding=UTF-8
android.useAndroidX=false
""")

w("app/build.gradle", r"""plugins {
    id 'com.android.application'
}

android {
    namespace 'app.contodo'
    compileSdk 35

    defaultConfig {
        applicationId 'app.contodo'
        minSdk 24
        targetSdk 34
        versionCode Integer.parseInt(System.getenv('VERSION_CODE') ?: '1')
        versionName '1.0.' + (System.getenv('VERSION_CODE') ?: '1')
    }

    signingConfigs {
        release {
            storeFile file('../contodo.jks')
            storePassword 'contodo-key'
            keyAlias 'contodo'
            keyPassword 'contodo-key'
        }
    }

    buildTypes {
        release {
            signingConfig signingConfigs.release
            minifyEnabled false
        }
    }

    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }

    lint {
        abortOnError false
        checkReleaseBuilds false
    }
}

tasks.withType(JavaCompile) {
    options.encoding = 'UTF-8'
}
""")

# ---------------------------------------------------------------- manifest
w("app/src/main/AndroidManifest.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.VIBRATE" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.USE_EXACT_ALARM" />
    <uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" android:maxSdkVersion="32" />

    <application
        android:allowBackup="false"
        android:icon="@mipmap/ic_launcher"
        android:label="ConTodo"
        android:theme="@style/AppTheme"
        android:usesCleartextTraffic="false">

        <activity
            android:name=".MainActivity"
            android:configChanges="orientation|screenSize|keyboard|keyboardHidden|smallestScreenSize|screenLayout|uiMode|density"
            android:exported="true"
            android:launchMode="singleTask"
            android:screenOrientation="portrait"
            android:windowSoftInputMode="adjustResize">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <receiver
            android:name=".CalendarWidget"
            android:exported="true"
            android:label="ConTodo カレンダー">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
            </intent-filter>
            <meta-data
                android:name="android.appwidget.provider"
                android:resource="@xml/calendar_widget_info" />
        </receiver>

        <receiver
            android:name=".PomodoroWidget"
            android:exported="true"
            android:label="ConTodo ポモドーロ">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
            </intent-filter>
            <meta-data
                android:name="android.appwidget.provider"
                android:resource="@xml/pomodoro_widget_info" />
        </receiver>

        <receiver
            android:name=".AlarmReceiver"
            android:exported="false" />
    </application>
</manifest>
""")

# ---------------------------------------------------------------- java
w(PKG_DIR + "/W.java", r"""package app.contodo;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;

import org.json.JSONObject;

import java.util.Locale;

final class W {
    private W() { }

    static SharedPreferences p(Context c) {
        return c.getSharedPreferences("c", Context.MODE_PRIVATE);
    }

    static JSONObject snap(Context c) {
        try {
            return new JSONObject(p(c).getString("snap", "{}"));
        } catch (Exception e) {
            return new JSONObject();
        }
    }

    static JSONObject theme(JSONObject snap) {
        JSONObject t = snap.optJSONObject("theme");
        return t != null ? t : new JSONObject();
    }

    static int parse(String s, int def) {
        try {
            if (s != null && s.trim().length() > 0) return Color.parseColor(s.trim());
        } catch (Exception e) {
            // 色として読めないときは既定の色を使う
        }
        return def;
    }

    static int col(JSONObject th, String key, int def) {
        return parse(th.optString(key, ""), def);
    }

    static String key(int y, int m, int d) {
        return String.format(Locale.US, "%04d-%02d-%02d", y, m, d);
    }

    // ウィジェットからアプリを開く。action はアプリ側の __conAction に渡る
    static PendingIntent open(Context c, String action, int requestCode) {
        Intent i = new Intent(c, MainActivity.class);
        i.putExtra("action", action);
        i.setData(Uri.parse("contodo://" + action));
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        return PendingIntent.getActivity(c, requestCode, i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    // タイマーの終了時刻を過ぎたら「おわり」の状態にする
    static void markFinished(Context c) {
        try {
            JSONObject o = snap(c);
            JSONObject t = o.optJSONObject("timer");
            if (t != null && t.optBoolean("running")) {
                t.put("running", false);
                t.put("finished", true);
                t.put("left", 0);
                p(c).edit().putString("snap", o.toString()).apply();
            }
        } catch (Exception e) {
            // 保存できなくても通知は出す
        }
    }
}
""")

w(PKG_DIR + "/Widgets.java", r"""package app.contodo;

import android.appwidget.AppWidgetManager;
import android.content.ComponentName;
import android.content.Context;

final class Widgets {
    private Widgets() { }

    static void updateAll(Context c) {
        try {
            AppWidgetManager m = AppWidgetManager.getInstance(c);
            int[] cal = m.getAppWidgetIds(new ComponentName(c, CalendarWidget.class));
            if (cal.length > 0) CalendarWidget.render(c, m, cal);
            int[] pomo = m.getAppWidgetIds(new ComponentName(c, PomodoroWidget.class));
            if (pomo.length > 0) PomodoroWidget.render(c, m, pomo);
        } catch (Exception e) {
            // ウィジェットの更新に失敗してもアプリは止めない
        }
    }
}
""")

w(PKG_DIR + "/Notifier.java", r"""package app.contodo;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.os.Build;

final class Notifier {
    static final String CHANNEL = "timer_v1";
    static final int ID = 1;
    private static final long[] PATTERN = {0, 260, 120, 260, 120, 520};

    private Notifier() { }

    static void show(Context c, String phase) {
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, "タイマー", NotificationManager.IMPORTANCE_HIGH);
            ch.enableVibration(true);
            ch.setVibrationPattern(PATTERN);
            nm.createNotificationChannel(ch);
        }
        String title;
        String body;
        if ("short".equals(phase) || "long".equals(phase)) {
            title = "休憩おわり";
            body = "次の一歩へ戻りましょう。";
        } else if ("quick".equals(phase)) {
            title = "5分できました";
            body = "続けるなら、もう一度はじめましょう。";
        } else {
            title = "集中おわり";
            body = "少し休みましょう。";
        }
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(c, CHANNEL)
                : new Notification.Builder(c);
        b.setSmallIcon(R.drawable.ic_notify)
                .setContentTitle(title)
                .setContentText(body)
                .setAutoCancel(true)
                .setContentIntent(W.open(c, "timer", 7));
        if (Build.VERSION.SDK_INT < 26) {
            b.setPriority(Notification.PRIORITY_HIGH)
                    .setVibrate(PATTERN)
                    .setDefaults(Notification.DEFAULT_SOUND);
        }
        nm.notify(ID, b.build());
    }
}
""")

w(PKG_DIR + "/TimerAlarm.java", r"""package app.contodo;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

import org.json.JSONObject;

final class TimerAlarm {
    private TimerAlarm() { }

    // アプリから届いたタイマーの状態に合わせて、終了時刻のアラームを付け替える
    static void sync(Context c, String json) {
        try {
            JSONObject t = new JSONObject(json).optJSONObject("timer");
            AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
            if (am == null) return;
            Intent i = new Intent(c, AlarmReceiver.class);
            i.putExtra("phase", t != null ? t.optString("phase", "focus") : "focus");
            PendingIntent pi = PendingIntent.getBroadcast(c, 100, i,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            long endAt = t != null ? t.optLong("endAt", 0) : 0;
            if (t != null && t.optBoolean("running") && endAt > System.currentTimeMillis()) {
                try {
                    if (Build.VERSION.SDK_INT >= 31 && !am.canScheduleExactAlarms()) {
                        am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, endAt, pi);
                    } else {
                        am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, endAt, pi);
                    }
                } catch (SecurityException e) {
                    am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, endAt, pi);
                }
            } else {
                am.cancel(pi);
            }
        } catch (Exception e) {
            // アラームを付けられなくても、アプリの中のタイマーは動く
        }
    }
}
""")

w(PKG_DIR + "/AlarmReceiver.java", r"""package app.contodo;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class AlarmReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        String phase = i.getStringExtra("phase");
        W.markFinished(c);
        // アプリを開いている間は、アプリ自身が音と振動で知らせる
        if (!MainActivity.foreground) Notifier.show(c, phase);
        Widgets.updateAll(c);
    }
}
""")

w(PKG_DIR + "/MainActivity.java", r"""package app.contodo;

import android.Manifest;
import android.app.Activity;
import android.app.NotificationManager;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    static final String BASE = "https://aji-daze.github.io/chakushu/";
    static final int REQ_FILE = 1;
    static final int REQ_SAVE = 2;
    static final int REQ_NOTIF = 3;
    static volatile boolean foreground = false;

    private WebView web;
    private ValueCallback<Uri[]> chooser;
    private String pendingContent;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        int bar = W.parse(W.p(this).getString("bar", ""), 0xFFF5F6F5);
        web = new WebView(this);
        web.setBackgroundColor(bar);
        setContentView(web);
        applyBars(bar);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setSupportZoom(false);
        s.setTextZoom(100);
        WebView.setWebContentsDebuggingEnabled(true);

        web.addJavascriptInterface(new Bridge(), "ConTodoNative");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if ("aji-daze.github.io".equals(u.getHost())) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, u));
                } catch (ActivityNotFoundException e) {
                    // 開けるアプリがなければ何もしない
                }
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams params) {
                if (chooser != null) chooser.onReceiveValue(null);
                chooser = cb;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                try {
                    startActivityForResult(Intent.createChooser(i, "バックアップを選ぶ"), REQ_FILE);
                } catch (Exception e) {
                    chooser = null;
                    return false;
                }
                return true;
            }
        });

        String action = clean(getIntent().getStringExtra("action"));
        web.loadUrl(BASE + (action.isEmpty() ? "" : "?action=" + action));

        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIF);
        }
    }

    static String clean(String a) {
        return a == null ? "" : a.replaceAll("[^a-z0-9]", "");
    }

    @Override
    protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        setIntent(i);
        String a = clean(i.getStringExtra("action"));
        if (!a.isEmpty() && web != null) {
            web.evaluateJavascript("window.__conAction&&window.__conAction('" + a + "')", null);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        foreground = true;
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm != null) nm.cancel(Notifier.ID);
    }

    @Override
    protected void onPause() {
        foreground = false;
        super.onPause();
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else moveTaskToBack(true);
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req == REQ_FILE) {
            if (chooser != null) {
                chooser.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(res, data));
                chooser = null;
            }
        } else if (req == REQ_SAVE) {
            if (res == RESULT_OK && data != null && data.getData() != null && pendingContent != null) {
                try {
                    OutputStream o = getContentResolver().openOutputStream(data.getData(), "w");
                    o.write(pendingContent.getBytes(StandardCharsets.UTF_8));
                    o.close();
                    Toast.makeText(this, "バックアップを保存しました", Toast.LENGTH_SHORT).show();
                } catch (Exception e) {
                    Toast.makeText(this, "保存できませんでした", Toast.LENGTH_LONG).show();
                }
            }
            pendingContent = null;
        }
    }

    // ステータスバーとナビゲーションバーを、アプリのテーマの色に合わせる
    void applyBars(int c) {
        try {
            getWindow().setStatusBarColor(c);
            getWindow().setNavigationBarColor(c);
            boolean light = (Color.red(c) * 299 + Color.green(c) * 587 + Color.blue(c) * 114) / 1000 > 150;
            View d = getWindow().getDecorView();
            int f = d.getSystemUiVisibility();
            int mask = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            if (Build.VERSION.SDK_INT >= 26) mask |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            d.setSystemUiVisibility(light ? (f | mask) : (f & ~mask));
            if (web != null) web.setBackgroundColor(c);
        } catch (Exception e) {
            // 色の反映に失敗しても動作には影響しない
        }
    }

    // ページ（ConTodo）から呼ばれる窓口。window.ConTodoNative として見える
    class Bridge {
        @JavascriptInterface
        public void update(String json) {
            W.p(MainActivity.this).edit().putString("snap", json).apply();
            TimerAlarm.sync(MainActivity.this, json);
            Widgets.updateAll(MainActivity.this);
        }

        @JavascriptInterface
        public void vibrate(String csv) {
            try {
                String[] parts = csv.split(",");
                long[] pattern = new long[parts.length + 1];
                pattern[0] = 0;
                for (int k = 0; k < parts.length; k++) pattern[k + 1] = Long.parseLong(parts[k].trim());
                Vibrator v = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
                if (v == null) return;
                if (Build.VERSION.SDK_INT >= 26) v.vibrate(VibrationEffect.createWaveform(pattern, -1));
                else v.vibrate(pattern, -1);
            } catch (Exception e) {
                // 振動できない端末では何もしない
            }
        }

        @JavascriptInterface
        public void setBars(String hex) {
            final int c = W.parse(hex, 0xFFF5F6F5);
            W.p(MainActivity.this).edit().putString("bar", hex).apply();
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    applyBars(c);
                }
            });
        }

        @JavascriptInterface
        public void saveBackup(final String name, final String json) {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    pendingContent = json;
                    Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    i.addCategory(Intent.CATEGORY_OPENABLE);
                    i.setType("application/json");
                    i.putExtra(Intent.EXTRA_TITLE, name);
                    try {
                        startActivityForResult(i, REQ_SAVE);
                    } catch (Exception e) {
                        pendingContent = null;
                        Toast.makeText(MainActivity.this, "保存先を開けませんでした", Toast.LENGTH_LONG).show();
                    }
                }
            });
        }
    }
}
""")

w(PKG_DIR + "/CalendarWidget.java", r"""package app.contodo;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.res.Resources;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.style.ForegroundColorSpan;
import android.text.style.RelativeSizeSpan;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Calendar;

public class CalendarWidget extends AppWidgetProvider {
    static final String ACT_PREV = "app.contodo.CAL_PREV";
    static final String ACT_NEXT = "app.contodo.CAL_NEXT";
    static final String ACT_HOME = "app.contodo.CAL_HOME";

    @Override
    public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        render(c, m, ids);
    }

    @Override
    public void onReceive(Context c, Intent i) {
        String a = i.getAction();
        if (ACT_PREV.equals(a) || ACT_NEXT.equals(a) || ACT_HOME.equals(a)) {
            int off = W.p(c).getInt("calOff", 0);
            if (ACT_PREV.equals(a)) off--;
            else if (ACT_NEXT.equals(a)) off++;
            else off = 0;
            off = Math.max(-12, Math.min(12, off));
            W.p(c).edit().putInt("calOff", off).apply();
            AppWidgetManager m = AppWidgetManager.getInstance(c);
            render(c, m, m.getAppWidgetIds(new ComponentName(c, CalendarWidget.class)));
            return;
        }
        super.onReceive(c, i);
    }

    private static PendingIntent broadcast(Context c, String action, int rc) {
        Intent i = new Intent(c, CalendarWidget.class);
        i.setAction(action);
        return PendingIntent.getBroadcast(c, rc, i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private static void dot(SpannableStringBuilder sb, int color) {
        int a = sb.length();
        sb.append("●");
        sb.setSpan(new ForegroundColorSpan(color), a, sb.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
    }

    static void render(Context c, AppWidgetManager m, int[] ids) {
        if (ids == null || ids.length == 0) return;
        JSONObject snap = W.snap(c);
        JSONObject th = W.theme(snap);
        int bg = W.col(th, "bg", 0xFFF5F6F5);
        int ink = W.col(th, "ink", 0xFF1D2120);
        int ink2 = W.col(th, "ink2", 0xFF6B716E);
        int ink3 = W.col(th, "ink3", 0xFFA2A7A4);
        int accent = W.col(th, "accent", 0xFF2F4B6E);
        int sun = W.col(th, "sun", 0xFFA5473A);
        int sat = W.col(th, "sat", 0xFF2F4B6E);
        JSONObject days = snap.optJSONObject("days");

        int off = W.p(c).getInt("calOff", 0);
        Calendar now = Calendar.getInstance();
        String todayKey = W.key(now.get(Calendar.YEAR), now.get(Calendar.MONTH) + 1, now.get(Calendar.DAY_OF_MONTH));
        Calendar first = Calendar.getInstance();
        first.set(Calendar.DAY_OF_MONTH, 1);
        first.set(Calendar.HOUR_OF_DAY, 12);
        first.add(Calendar.MONTH, off);
        int y = first.get(Calendar.YEAR);
        int mo = first.get(Calendar.MONTH) + 1;
        int startDow = first.get(Calendar.DAY_OF_WEEK) - 1;

        Resources res = c.getResources();
        String pkg = c.getPackageName();
        RemoteViews v = new RemoteViews(pkg, R.layout.widget_calendar);
        v.setInt(R.id.bg, "setColorFilter", bg);

        v.setTextViewText(R.id.cal_title, y + "年" + mo + "月");
        v.setTextColor(R.id.cal_title, ink);
        v.setTextColor(R.id.cal_prev, ink2);
        v.setTextColor(R.id.cal_next, ink2);
        v.setOnClickPendingIntent(R.id.cal_prev, broadcast(c, ACT_PREV, 11));
        v.setOnClickPendingIntent(R.id.cal_next, broadcast(c, ACT_NEXT, 12));
        v.setOnClickPendingIntent(R.id.cal_title, off != 0 ? broadcast(c, ACT_HOME, 13) : W.open(c, "cal", 14));
        v.setOnClickPendingIntent(R.id.root, W.open(c, "cal", 15));

        for (int i = 0; i < 7; i++) {
            int id = res.getIdentifier("wk" + i, "id", pkg);
            v.setTextColor(id, i == 0 ? sun : (i == 6 ? sat : ink3));
        }

        for (int r = 0; r < 6; r++) {
            for (int cc = 0; cc < 7; cc++) {
                int idx = r * 7 + cc;
                Calendar d = (Calendar) first.clone();
                d.add(Calendar.DAY_OF_MONTH, idx - startDow);
                boolean out = d.get(Calendar.MONTH) + 1 != mo;
                String key = W.key(d.get(Calendar.YEAR), d.get(Calendar.MONTH) + 1, d.get(Calendar.DAY_OF_MONTH));
                boolean isToday = key.equals(todayKey);

                SpannableStringBuilder sb = new SpannableStringBuilder(String.valueOf(d.get(Calendar.DAY_OF_MONTH)));
                sb.append("\n");
                int s0 = sb.length();
                JSONObject info = (!out && days != null) ? days.optJSONObject(key) : null;
                int n = 0;
                if (info != null) {
                    JSONArray sa = info.optJSONArray("s");
                    if (sa != null) {
                        for (int k = 0; k < sa.length() && k < 2; k++) {
                            dot(sb, isToday ? bg : W.parse(sa.optString(k), ink2));
                            n++;
                        }
                    }
                    if (info.optInt("e", 0) > 0) {
                        dot(sb, isToday ? bg : ink2);
                        n++;
                    }
                }
                if (n == 0) sb.append(" ");
                sb.setSpan(new RelativeSizeSpan(0.6f), s0, sb.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);

                int cid = res.getIdentifier("c" + r + cc, "id", pkg);
                v.setTextViewText(cid, sb);
                int color = out ? ink3 : (cc == 0 ? sun : (cc == 6 ? sat : ink));
                if (isToday) {
                    v.setInt(cid, "setBackgroundColor", accent);
                    color = bg;
                }
                v.setTextColor(cid, color);
            }
        }

        // 今日の予定・シフト
        SpannableStringBuilder list = new SpannableStringBuilder();
        JSONObject td = days != null ? days.optJSONObject(todayKey) : null;
        JSONArray items = td != null ? td.optJSONArray("l") : null;
        if (items != null && items.length() > 0) {
            int n = Math.min(3, items.length());
            for (int k = 0; k < n; k++) {
                JSONArray it = items.optJSONArray(k);
                if (it == null) continue;
                int a = list.length();
                list.append("● ");
                list.setSpan(new ForegroundColorSpan(W.parse(it.optString(2, ""), ink2)), a, a + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                list.append(it.optString(0)).append("  ").append(it.optString(1));
                if (k < n - 1) list.append("\n");
            }
            if (items.length() > 3) list.append("\n他 " + (items.length() - 3) + " 件");
        } else {
            list.append("今日の予定はありません");
        }
        v.setTextViewText(R.id.cal_list, list);
        v.setTextColor(R.id.cal_list, ink);

        m.updateAppWidget(ids, v);
    }
}
""")

w(PKG_DIR + "/PomodoroWidget.java", r"""package app.contodo;

import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.os.SystemClock;
import android.view.View;
import android.widget.RemoteViews;

import org.json.JSONObject;

import java.util.Calendar;
import java.util.Locale;

public class PomodoroWidget extends AppWidgetProvider {
    @Override
    public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        render(c, m, ids);
    }

    static void render(Context c, AppWidgetManager m, int[] ids) {
        if (ids == null || ids.length == 0) return;
        JSONObject snap = W.snap(c);
        JSONObject th = W.theme(snap);
        int bg = W.col(th, "bg", 0xFFF5F6F5);
        int ink = W.col(th, "ink", 0xFF1D2120);
        int ink2 = W.col(th, "ink2", 0xFF6B716E);
        int ink3 = W.col(th, "ink3", 0xFFA2A7A4);
        int accent = W.col(th, "accent", 0xFF2F4B6E);
        int rest = W.col(th, "rest", 0xFF557F6A);

        JSONObject t = snap.optJSONObject("timer");
        boolean has = t != null;
        String phase = has ? t.optString("phase", "focus") : "focus";
        boolean isBreak = "short".equals(phase) || "long".equals(phase);
        boolean running = has && t.optBoolean("running");
        boolean finished = has && t.optBoolean("finished");
        long endAt = has ? t.optLong("endAt", 0) : 0;
        long now = System.currentTimeMillis();
        if (running && endAt <= now) {
            running = false;
            finished = true;
        }
        int leftSec = has ? t.optInt("left", 1500) : 1500;
        if (finished) leftSec = 0;
        String label = finished ? "おわり" : (has ? t.optString("label", "集中") : "集中");

        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget_pomo);
        v.setInt(R.id.bg, "setColorFilter", bg);

        v.setTextViewText(R.id.pomo_phase, label);
        v.setTextColor(R.id.pomo_phase, isBreak ? rest : accent);

        if (running) {
            v.setViewVisibility(R.id.pomo_chrono, View.VISIBLE);
            v.setViewVisibility(R.id.pomo_time, View.GONE);
            long base = SystemClock.elapsedRealtime() + (endAt - now);
            v.setChronometer(R.id.pomo_chrono, base, null, true);
            v.setChronometerCountDown(R.id.pomo_chrono, true);
            v.setTextColor(R.id.pomo_chrono, ink);
        } else {
            v.setViewVisibility(R.id.pomo_chrono, View.GONE);
            v.setViewVisibility(R.id.pomo_time, View.VISIBLE);
            v.setTextViewText(R.id.pomo_time, String.format(Locale.US, "%02d:%02d", leftSec / 60, leftSec % 60));
            v.setTextColor(R.id.pomo_time, ink);
        }

        Calendar cal = Calendar.getInstance();
        String todayKey = W.key(cal.get(Calendar.YEAR), cal.get(Calendar.MONTH) + 1, cal.get(Calendar.DAY_OF_MONTH));
        JSONObject td = snap.optJSONObject("today");
        int pomos = 0;
        int min = 0;
        if (td != null && todayKey.equals(snap.optString("todayKey"))) {
            pomos = td.optInt("pomos");
            min = td.optInt("min");
        }
        v.setTextViewText(R.id.pomo_sub, "今日 " + pomos + "回・" + min + "分");
        v.setTextColor(R.id.pomo_sub, ink2);

        int every = has ? Math.max(1, Math.min(8, t.optInt("every", 4))) : 4;
        int round = has ? t.optInt("round", 0) : 0;
        if ("long".equals(phase)) round = every;
        StringBuilder dots = new StringBuilder();
        for (int k = 0; k < every; k++) {
            if (k > 0) dots.append(' ');
            dots.append(k < round ? "●" : "○");
        }
        v.setTextViewText(R.id.pomo_dots, dots.toString());
        v.setTextColor(R.id.pomo_dots, ink3);

        boolean open = running || finished;
        v.setInt(R.id.pomo_btnbg, "setColorFilter", ink);
        v.setTextViewText(R.id.pomo_btn, open ? "開く" : "▶ 始める");
        v.setTextColor(R.id.pomo_btn, bg);
        v.setOnClickPendingIntent(R.id.pomo_btnbox, W.open(c, open ? "timer" : "start", 21));
        v.setOnClickPendingIntent(R.id.root, W.open(c, "timer", 22));

        m.updateAppWidget(ids, v);
    }
}
""")

# ---------------------------------------------------------------- res
w(RES + "/values/strings.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">ConTodo</string>
    <string name="widget_calendar_desc">月のカレンダーと、今日の予定・シフト</string>
    <string name="widget_pomodoro_desc">ポモドーロのタイマーと、今日の進み具合</string>
</resources>
""")

w(RES + "/values/colors.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="app_bg">#F5F6F5</color>
</resources>
""")

w(RES + "/values/styles.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="AppTheme" parent="android:Theme.DeviceDefault.NoActionBar">
        <item name="android:windowBackground">@color/app_bg</item>
        <item name="android:statusBarColor">@color/app_bg</item>
        <item name="android:navigationBarColor">@color/app_bg</item>
        <item name="android:windowLightStatusBar">true</item>
    </style>
</resources>
""")

w(RES + "/drawable/w_round.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#FFFFFFFF" />
    <corners android:radius="22dp" />
</shape>
""")

w(RES + "/drawable/w_pill.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#FFFFFFFF" />
    <corners android:radius="20dp" />
</shape>
""")

w(RES + "/drawable/ic_notify.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FFFFFFFF"
        android:fillType="evenOdd"
        android:pathData="M12,3C7.03,3 3,7.03 3,12s4.03,9 9,9 9,-4.03 9,-9 -4.03,-9 -9,-9zM12,6c-3.31,0 -6,2.69 -6,6s2.69,6 6,6 6,-2.69 6,-6 -2.69,-6 -6,-6z" />
</vector>
""")

w(RES + "/xml/calendar_widget_info.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    android:description="@string/widget_calendar_desc"
    android:initialLayout="@layout/widget_calendar"
    android:minWidth="250dp"
    android:minHeight="250dp"
    android:minResizeWidth="180dp"
    android:minResizeHeight="180dp"
    android:resizeMode="horizontal|vertical"
    android:targetCellWidth="4"
    android:targetCellHeight="4"
    android:updatePeriodMillis="1800000"
    android:widgetCategory="home_screen" />
""")

w(RES + "/xml/pomodoro_widget_info.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    android:description="@string/widget_pomodoro_desc"
    android:initialLayout="@layout/widget_pomo"
    android:minWidth="180dp"
    android:minHeight="110dp"
    android:minResizeWidth="180dp"
    android:minResizeHeight="110dp"
    android:resizeMode="horizontal|vertical"
    android:targetCellWidth="3"
    android:targetCellHeight="2"
    android:updatePeriodMillis="1800000"
    android:widgetCategory="home_screen" />
""")

# カレンダー：6週 x 7日のマスを並べる
weekdays = "".join(
    '        <TextView\n'
    '            android:id="@+id/wk%d"\n'
    '            android:layout_width="0dp"\n'
    '            android:layout_height="wrap_content"\n'
    '            android:layout_weight="1"\n'
    '            android:gravity="center"\n'
    '            android:text="%s"\n'
    '            android:textSize="10sp" />\n' % (i, d)
    for i, d in enumerate("日月火水木金土")
)
rows = ""
for r in range(6):
    cells = "".join(
        '        <TextView\n'
        '            android:id="@+id/c%d%d"\n'
        '            android:layout_width="0dp"\n'
        '            android:layout_height="match_parent"\n'
        '            android:layout_weight="1"\n'
        '            android:gravity="center"\n'
        '            android:includeFontPadding="false"\n'
        '            android:lineSpacingMultiplier="0.85"\n'
        '            android:maxLines="2"\n'
        '            android:textSize="11sp" />\n' % (r, c)
        for c in range(7)
    )
    rows += (
        '    <LinearLayout\n'
        '        android:layout_width="match_parent"\n'
        '        android:layout_height="0dp"\n'
        '        android:layout_weight="1"\n'
        '        android:orientation="horizontal">\n' + cells + '    </LinearLayout>\n'
    )

w(RES + "/layout/widget_calendar.xml",
  '<?xml version="1.0" encoding="utf-8"?>\n'
  '<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"\n'
  '    android:id="@+id/root"\n'
  '    android:layout_width="match_parent"\n'
  '    android:layout_height="match_parent">\n'
  '\n'
  '    <ImageView\n'
  '        android:id="@+id/bg"\n'
  '        android:layout_width="match_parent"\n'
  '        android:layout_height="match_parent"\n'
  '        android:scaleType="fitXY"\n'
  '        android:src="@drawable/w_round" />\n'
  '\n'
  '    <LinearLayout\n'
  '        android:layout_width="match_parent"\n'
  '        android:layout_height="match_parent"\n'
  '        android:orientation="vertical"\n'
  '        android:padding="10dp">\n'
  '\n'
  '        <LinearLayout\n'
  '            android:layout_width="match_parent"\n'
  '            android:layout_height="wrap_content"\n'
  '            android:gravity="center_vertical"\n'
  '            android:orientation="horizontal">\n'
  '\n'
  '            <TextView\n'
  '                android:id="@+id/cal_title"\n'
  '                android:layout_width="0dp"\n'
  '                android:layout_height="wrap_content"\n'
  '                android:layout_weight="1"\n'
  '                android:paddingStart="4dp"\n'
  '                android:paddingTop="2dp"\n'
  '                android:paddingBottom="2dp"\n'
  '                android:text="ConTodo"\n'
  '                android:textSize="16sp"\n'
  '                android:textStyle="bold" />\n'
  '\n'
  '            <TextView\n'
  '                android:id="@+id/cal_prev"\n'
  '                android:layout_width="wrap_content"\n'
  '                android:layout_height="wrap_content"\n'
  '                android:paddingStart="12dp"\n'
  '                android:paddingEnd="12dp"\n'
  '                android:text="‹"\n'
  '                android:textSize="22sp" />\n'
  '\n'
  '            <TextView\n'
  '                android:id="@+id/cal_next"\n'
  '                android:layout_width="wrap_content"\n'
  '                android:layout_height="wrap_content"\n'
  '                android:paddingStart="12dp"\n'
  '                android:paddingEnd="8dp"\n'
  '                android:text="›"\n'
  '                android:textSize="22sp" />\n'
  '        </LinearLayout>\n'
  '\n'
  '        <LinearLayout\n'
  '            android:layout_width="match_parent"\n'
  '            android:layout_height="wrap_content"\n'
  '            android:orientation="horizontal">\n'
  + weekdays +
  '        </LinearLayout>\n'
  '\n'
  + rows +
  '\n'
  '    <TextView\n'
  '        android:id="@+id/cal_list"\n'
  '        android:layout_width="match_parent"\n'
  '        android:layout_height="wrap_content"\n'
  '        android:maxLines="4"\n'
  '        android:paddingStart="4dp"\n'
  '        android:paddingTop="6dp"\n'
  '        android:textSize="11sp" />\n'
  '    </LinearLayout>\n'
  '</FrameLayout>\n')

w(RES + "/layout/widget_pomo.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/root"
    android:layout_width="match_parent"
    android:layout_height="match_parent">

    <ImageView
        android:id="@+id/bg"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:scaleType="fitXY"
        android:src="@drawable/w_round" />

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:gravity="center_vertical"
        android:orientation="horizontal"
        android:padding="14dp">

        <LinearLayout
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:orientation="vertical">

            <TextView
                android:id="@+id/pomo_phase"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:letterSpacing="0.2"
                android:text="集中"
                android:textSize="12sp" />

            <FrameLayout
                android:layout_width="wrap_content"
                android:layout_height="wrap_content">

                <Chronometer
                    android:id="@+id/pomo_chrono"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:fontFamily="sans-serif-light"
                    android:includeFontPadding="false"
                    android:textSize="38sp" />

                <TextView
                    android:id="@+id/pomo_time"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:fontFamily="sans-serif-light"
                    android:includeFontPadding="false"
                    android:text="25:00"
                    android:textSize="38sp" />
            </FrameLayout>

            <TextView
                android:id="@+id/pomo_sub"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:paddingTop="2dp"
                android:text="今日 0回・0分"
                android:textSize="11sp" />
        </LinearLayout>

        <LinearLayout
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:gravity="center_horizontal"
            android:orientation="vertical">

            <TextView
                android:id="@+id/pomo_dots"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:paddingBottom="8dp"
                android:text="○ ○ ○ ○"
                android:textSize="11sp" />

            <FrameLayout
                android:id="@+id/pomo_btnbox"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content">

                <ImageView
                    android:id="@+id/pomo_btnbg"
                    android:layout_width="match_parent"
                    android:layout_height="match_parent"
                    android:scaleType="fitXY"
                    android:src="@drawable/w_pill" />

                <TextView
                    android:id="@+id/pomo_btn"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:paddingStart="16dp"
                    android:paddingTop="9dp"
                    android:paddingEnd="16dp"
                    android:paddingBottom="9dp"
                    android:text="▶ 始める"
                    android:textSize="13sp" />
            </FrameLayout>
        </LinearLayout>
    </LinearLayout>
</FrameLayout>
""")

# ---------------------------------------------------------------- icon
# ランチャーアイコンは、公開中のアプリのアイコンをそのまま使う
icon_path = os.path.join(ROOT, RES, "mipmap-xxxhdpi", "ic_launcher.png")
os.makedirs(os.path.dirname(icon_path), exist_ok=True)
try:
    urllib.request.urlretrieve("https://aji-daze.github.io/chakushu/icon-512.png", icon_path)
except Exception as e:  # ネットワークに失敗したときは無地のアイコンで代用
    print("icon download failed:", e)
    with open(icon_path, "wb") as f:
        f.write(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="))

print("project written")
