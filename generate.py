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
            android:configChanges="orientation|screenSize|keyboard|keyboardHidden|smallestScreenSize|screenLayout|density"
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
            android:name=".TimelineWidget"
            android:exported="true"
            android:label="ConTodo 今日の流れ">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
            </intent-filter>
            <meta-data
                android:name="android.appwidget.provider"
                android:resource="@xml/timeline_widget_info" />
        </receiver>

        <receiver
            android:name=".TasksWidget"
            android:exported="true"
            android:label="ConTodo やること">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
            </intent-filter>
            <meta-data
                android:name="android.appwidget.provider"
                android:resource="@xml/tasks_widget_info" />
        </receiver>

        <receiver
            android:name=".FocusWidget"
            android:exported="true"
            android:label="ConTodo 集中">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
            </intent-filter>
            <meta-data
                android:name="android.appwidget.provider"
                android:resource="@xml/focus_widget_info" />
        </receiver>

        <receiver
            android:name=".MoneyWidget"
            android:exported="true"
            android:label="ConTodo 家計簿">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
            </intent-filter>
            <meta-data
                android:name="android.appwidget.provider"
                android:resource="@xml/money_widget_info" />
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
            int[] tl = m.getAppWidgetIds(new ComponentName(c, TimelineWidget.class));
            if (tl.length > 0) TimelineWidget.render(c, m, tl);
            int[] tasks = m.getAppWidgetIds(new ComponentName(c, TasksWidget.class));
            if (tasks.length > 0) TasksWidget.render(c, m, tasks);
            int[] focus = m.getAppWidgetIds(new ComponentName(c, FocusWidget.class));
            if (focus.length > 0) FocusWidget.render(c, m, focus);
            int[] money = m.getAppWidgetIds(new ComponentName(c, MoneyWidget.class));
            if (money.length > 0) MoneyWidget.render(c, m, money);
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

import org.json.JSONObject;

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
        // 色の切り替えはアプリ側（ConTodoのテーマ）に任せ、WebViewの自動ダーク化は使わない
        if (Build.VERSION.SDK_INT >= 29) s.setForceDark(WebSettings.FORCE_DARK_OFF);
        WebView.setWebContentsDebuggingEnabled(true);

        web.addJavascriptInterface(new Bridge(), "ConTodoNative");
        // DESK（/kb-cso/desk/）も同じ WebView で開く。DESK はこの名前で1日の要約を渡してくる
        web.addJavascriptInterface(new DeskBridge(), "DeskAndroid");
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
            String u = web.getUrl();
            // DESK を開いているときは ConTodo に戻してから操作する
            if (u == null || !u.startsWith(BASE)) web.loadUrl(BASE + "?action=" + a);
            else web.evaluateJavascript("window.__conAction&&window.__conAction('" + a + "')", null);
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
            android.content.SharedPreferences.Editor ed = W.p(MainActivity.this).edit().putString("snap", json);
            try {
                JSONObject d = new JSONObject(json).optJSONObject("desk");
                if (d != null) ed.putString("desk", d.toString());
            } catch (Exception e) {
                // 要約が読めなくても、ほかのウィジェットは更新する
            }
            ed.apply();
            TimerAlarm.sync(MainActivity.this, json);
            Widgets.updateAll(MainActivity.this);
        }

        @JavascriptInterface
        public void saveFile(final String name, final String mime, final String content) {
            startSave(name, mime, content);
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
            startSave(name, "application/json", json);
        }
    }

    // 端末の「保存先を選ぶ」画面を開き、選ばれた場所に書き込む（onActivityResult で書く）
    void startSave(final String name, final String mime, final String content) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                pendingContent = content;
                Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType(mime);
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

    // DESK の画面から呼ばれる窓口。window.DeskAndroid として見える
    class DeskBridge {
        @JavascriptInterface
        public void publish(String json) {
            W.p(MainActivity.this).edit().putString("desk", json).apply();
            Widgets.updateAll(MainActivity.this);
        }

        @JavascriptInterface
        public String version() {
            return "ConTodo " + Build.VERSION.SDK_INT;
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

# DESK から移したウィジェット（今日の流れ・やること・集中）と、家計簿のウィジェット。
# どれも同じ骨組み（widget_card）を使い、見出し・大きな数字・本文・下の一行を出し分ける。
w(PKG_DIR + "/Card.java", r"""package app.contodo;

import android.content.Context;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.style.ForegroundColorSpan;
import android.text.style.RelativeSizeSpan;
import android.view.View;
import android.widget.RemoteViews;

import org.json.JSONObject;

import java.util.Calendar;
import java.util.Locale;

final class Card {
    // DESK の半透明ウィジェットの色。壁紙が透ける前提で、白と1色だけに絞る
    static final int TEXT = 0xFFF3F3F5;
    static final int SUB = 0xA6F3F3F5;
    static final int FAINT = 0x66F3F3F5;
    static final int ACCENT = 0xFFE0A458;

    private Card() { }

    // DESK 用の要約。ConTodo の画面と DESK の画面のどちらからも届く
    static JSONObject desk(Context c) {
        try {
            return new JSONObject(W.p(c).getString("desk", "{}"));
        } catch (Exception e) {
            return new JSONObject();
        }
    }

    static boolean isToday(long at) {
        if (at <= 0) return false;
        Calendar a = Calendar.getInstance();
        a.setTimeInMillis(at);
        Calendar n = Calendar.getInstance();
        return a.get(Calendar.YEAR) == n.get(Calendar.YEAR) && a.get(Calendar.DAY_OF_YEAR) == n.get(Calendar.DAY_OF_YEAR);
    }

    static int toMin(String hm) {
        if (hm == null) return 0;
        String[] p = hm.split(":");
        try {
            return Integer.parseInt(p[0].trim()) * 60 + (p.length > 1 ? Integer.parseInt(p[1].trim()) : 0);
        } catch (Exception e) {
            return 0;
        }
    }

    static String hhmm(int min) {
        return String.format(Locale.US, "%d:%02d", (min / 60) % 24, min % 60);
    }

    static int nowMin() {
        Calendar c = Calendar.getInstance();
        return c.get(Calendar.HOUR_OF_DAY) * 60 + c.get(Calendar.MINUTE);
    }

    static String yen(long n) {
        return (n < 0 ? "−¥" : "¥") + String.format(Locale.JAPAN, "%,d", Math.abs(n));
    }

    static void color(SpannableStringBuilder sb, int from, int color) {
        sb.setSpan(new ForegroundColorSpan(color), from, sb.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
    }

    static void small(SpannableStringBuilder sb, int from) {
        sb.setSpan(new RelativeSizeSpan(0.85f), from, sb.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
    }

    // 半透明のカード（DESK 由来の3つ）
    static RemoteViews glass(Context c, String label, String action, int rc) {
        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget_card);
        v.setImageViewResource(R.id.bg, R.drawable.w_glass);
        v.setTextViewText(R.id.w_label, label);
        v.setTextColor(R.id.w_label, FAINT);
        v.setTextColor(R.id.w_right, FAINT);
        v.setTextColor(R.id.w_big, TEXT);
        v.setTextColor(R.id.w_unit, SUB);
        v.setTextColor(R.id.w_body, TEXT);
        v.setTextColor(R.id.w_foot, SUB);
        v.setViewVisibility(R.id.w_bigrow, View.GONE);
        v.setOnClickPendingIntent(R.id.root, W.open(c, action, rc));
        return v;
    }
}
""")

w(PKG_DIR + "/TimelineWidget.java", r"""package app.contodo;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.content.Intent;
import android.text.SpannableStringBuilder;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;

public class TimelineWidget extends AppWidgetProvider {
    static final String ACT_TICK = "app.contodo.TL_TICK";

    @Override
    public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        render(c, m, ids);
    }

    @Override
    public void onReceive(Context c, Intent i) {
        if (ACT_TICK.equals(i.getAction())) {
            Widgets.updateAll(c);
            return;
        }
        super.onReceive(c, i);
    }

    static void render(Context c, AppWidgetManager m, int[] ids) {
        if (ids == null || ids.length == 0) return;
        JSONObject d = Card.desk(c);
        boolean today = Card.isToday(d.optLong("at", 0));
        int now = Card.nowMin();

        // [開始, 終了, 題名]
        List<Object[]> blocks = new ArrayList<>();
        JSONArray arr = today ? d.optJSONArray("blocks") : null;
        if (arr != null) {
            for (int k = 0; k < arr.length(); k++) {
                JSONObject b = arr.optJSONObject(k);
                if (b == null) continue;
                int s = Card.toMin(b.optString("start"));
                int e = Card.toMin(b.optString("end"));
                if (e <= s) e += 1440; // 日をまたぐシフト
                blocks.add(new Object[]{s, e, b.optString("title", "（無題）")});
            }
        }

        Object[] cur = null;
        List<Object[]> next = new ArrayList<>();
        for (Object[] b : blocks) {
            int s = (Integer) b[0], e = (Integer) b[1];
            if (cur == null && s <= now && now < e) cur = b;
            else if (s > now) next.add(b);
        }

        Calendar cal = Calendar.getInstance();
        RemoteViews v = Card.glass(c, "今日の流れ", "desk", 31);
        v.setTextViewText(R.id.w_right, (cal.get(Calendar.MONTH) + 1) + "/" + cal.get(Calendar.DAY_OF_MONTH)
                + "（" + "日月火水木金土".charAt(cal.get(Calendar.DAY_OF_WEEK) - 1) + "）");

        SpannableStringBuilder sb = new SpannableStringBuilder();
        if (d.optLong("at", 0) == 0) {
            sb.append("アプリを一度開くと、ここに今日の予定が出る。");
            Card.color(sb, 0, Card.SUB);
        } else {
            if (cur != null) {
                sb.append("● ");
                Card.color(sb, 0, Card.ACCENT);
                sb.append((String) cur[2]).append("\n");
                int a = sb.length();
                sb.append(Card.hhmm((Integer) cur[0])).append("–").append(Card.hhmm((Integer) cur[1]));
                Card.color(sb, a, Card.SUB);
                Card.small(sb, a);
            } else {
                int a = sb.length();
                sb.append("いまは予定なし");
                Card.color(sb, a, Card.SUB);
            }
            for (int k = 0; k < next.size() && k < 3; k++) {
                sb.append("\n");
                int a = sb.length();
                sb.append(Card.hhmm((Integer) next.get(k)[0])).append("  ");
                Card.color(sb, a, Card.SUB);
                sb.append((String) next.get(k)[2]);
            }
            if (cur == null && next.isEmpty()) {
                sb.append("\n");
                int a = sb.length();
                sb.append("この先の予定もなし");
                Card.color(sb, a, Card.SUB);
            }
        }
        v.setTextViewText(R.id.w_body, sb);

        JSONObject f = d.optJSONObject("focus");
        int min = today && f != null ? f.optInt("min") : 0;
        v.setTextViewText(R.id.w_foot, "集中 " + min + " 分 ・ 残タスク " + d.optInt("remain", 0));
        m.updateAppWidget(ids, v);

        // 次の区切り（予定の始まり・終わり、または日付が変わる時刻）で描き直す
        int nextAt = 1440;
        for (Object[] b : blocks) {
            int s = (Integer) b[0], e = (Integer) b[1];
            if (s > now) nextAt = Math.min(nextAt, s);
            if (e > now) nextAt = Math.min(nextAt, e);
        }
        schedule(c, nextAt);
    }

    private static void schedule(Context c, int atMin) {
        try {
            AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
            if (am == null) return;
            Calendar t = Calendar.getInstance();
            t.set(Calendar.HOUR_OF_DAY, 0);
            t.set(Calendar.MINUTE, 0);
            t.set(Calendar.SECOND, 5);
            t.set(Calendar.MILLISECOND, 0);
            t.add(Calendar.MINUTE, atMin);
            Intent i = new Intent(c, TimelineWidget.class);
            i.setAction(ACT_TICK);
            PendingIntent pi = PendingIntent.getBroadcast(c, 300, i,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            // 端末を起こさない。画面がついたときに追いつけば足りる
            am.set(AlarmManager.RTC, t.getTimeInMillis(), pi);
        } catch (Exception e) {
            // 予約できなくても30分ごとの更新で追いつく
        }
    }
}
""")

w(PKG_DIR + "/TasksWidget.java", r"""package app.contodo;

import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.text.SpannableStringBuilder;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

public class TasksWidget extends AppWidgetProvider {
    @Override
    public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        render(c, m, ids);
    }

    static void render(Context c, AppWidgetManager m, int[] ids) {
        if (ids == null || ids.length == 0) return;
        JSONObject d = Card.desk(c);
        RemoteViews v = Card.glass(c, "やること", "tasks", 32);
        v.setTextViewText(R.id.w_right, String.valueOf(d.optInt("remain", 0)));

        SpannableStringBuilder sb = new SpannableStringBuilder();
        JSONArray arr = d.optJSONArray("tasks");
        if (arr == null || arr.length() == 0) {
            sb.append(d.optLong("at", 0) == 0 ? "アプリを一度開くと、ここに出る。" : "残っているタスクはない。");
            Card.color(sb, 0, Card.SUB);
        } else {
            int n = Math.min(5, arr.length());
            for (int k = 0; k < n; k++) {
                JSONObject t = arr.optJSONObject(k);
                if (t == null) continue;
                if (sb.length() > 0) sb.append("\n");
                int a = sb.length();
                sb.append("○  ");
                Card.color(sb, a, Card.SUB);
                sb.append(t.optString("text"));
                String step = t.optString("step", "");
                if (!step.isEmpty()) {
                    sb.append("\n");
                    int b = sb.length();
                    sb.append("    → ").append(step);
                    Card.color(sb, b, Card.SUB);
                    Card.small(sb, b);
                }
            }
        }
        v.setTextViewText(R.id.w_body, sb);
        v.setTextViewText(R.id.w_foot, "");
        m.updateAppWidget(ids, v);
    }
}
""")

w(PKG_DIR + "/FocusWidget.java", r"""package app.contodo;

import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.view.View;
import android.widget.RemoteViews;

import org.json.JSONObject;

public class FocusWidget extends AppWidgetProvider {
    @Override
    public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        render(c, m, ids);
    }

    static void render(Context c, AppWidgetManager m, int[] ids) {
        if (ids == null || ids.length == 0) return;
        JSONObject d = Card.desk(c);
        boolean today = Card.isToday(d.optLong("at", 0));
        JSONObject f = d.optJSONObject("focus");
        int min = today && f != null ? f.optInt("min") : 0;
        int count = today && f != null ? f.optInt("count") : 0;
        int streak = f != null ? f.optInt("streak") : 0;

        // タイマーが動いているかは、ConTodo 本体の状態を見る
        JSONObject t = W.snap(c).optJSONObject("timer");
        boolean running = t != null && t.optBoolean("running") && t.optLong("endAt", 0) > System.currentTimeMillis();

        RemoteViews v = Card.glass(c, "集中", "timer", 33);
        v.setTextViewText(R.id.w_right, running ? "進行中" : "");
        v.setTextColor(R.id.w_right, Card.ACCENT);
        v.setViewVisibility(R.id.w_bigrow, View.VISIBLE);
        v.setTextViewText(R.id.w_big, String.valueOf(min));
        v.setTextViewText(R.id.w_unit, "分");
        v.setTextViewText(R.id.w_body, "今日 " + count + " 本 ・ 連続 " + streak + " 日");
        v.setTextColor(R.id.w_body, Card.SUB);
        v.setTextViewText(R.id.w_foot, "終業 " + Card.hhmm(Card.toMin(d.optString("dayEnd", "18:00"))));
        m.updateAppWidget(ids, v);
    }
}
""")

w(PKG_DIR + "/MoneyWidget.java", r"""package app.contodo;

import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.text.SpannableStringBuilder;
import android.view.View;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Calendar;
import java.util.Locale;

// 家計簿：今月の支出、予算の残り、多いカテゴリ。色は ConTodo のテーマに合わせる
public class MoneyWidget extends AppWidgetProvider {
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
        int danger = W.col(th, "sun", 0xFFA5473A);

        Calendar cal = Calendar.getInstance();
        String ym = String.format(Locale.US, "%04d-%02d", cal.get(Calendar.YEAR), cal.get(Calendar.MONTH) + 1);
        JSONObject mo = snap.optJSONObject("money");
        // 月が変わった直後は、アプリを開くまで前の月の数字を出さない
        if (mo != null && !ym.equals(mo.optString("ym"))) mo = null;

        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget_card);
        v.setImageViewResource(R.id.bg, R.drawable.w_round);
        v.setInt(R.id.bg, "setColorFilter", bg);
        v.setTextViewText(R.id.w_label, (cal.get(Calendar.MONTH) + 1) + "月の支出");
        v.setTextColor(R.id.w_label, ink3);
        v.setViewVisibility(R.id.w_bigrow, View.VISIBLE);
        v.setTextViewText(R.id.w_big, Card.yen(mo != null ? mo.optLong("total") : 0));
        v.setTextColor(R.id.w_big, ink);
        v.setTextViewText(R.id.w_unit, "");
        v.setTextViewText(R.id.w_right, mo != null ? mo.optInt("count") + "件" : "");
        v.setTextColor(R.id.w_right, ink3);

        SpannableStringBuilder sb = new SpannableStringBuilder();
        if (mo != null && mo.optLong("budget") > 0) {
            long left = mo.optLong("left");
            int a = sb.length();
            if (left < 0) {
                sb.append("予算を ").append(Card.yen(-left)).append(" 超えています");
                Card.color(sb, a, danger);
            } else {
                sb.append("残り ").append(Card.yen(left));
                if (mo.optInt("days") > 0) sb.append(" ・ 1日 ").append(Card.yen(mo.optLong("perDay")));
                Card.color(sb, a, ink2);
            }
        }
        JSONArray cats = mo != null ? mo.optJSONArray("cats") : null;
        if (cats != null) {
            for (int k = 0; k < cats.length(); k++) {
                JSONArray it = cats.optJSONArray(k);
                if (it == null) continue;
                if (sb.length() > 0) sb.append("\n");
                int a = sb.length();
                sb.append("● ");
                Card.color(sb, a, W.parse(it.optString(2), ink2));
                sb.append(it.optString(0)).append("  ");
                int b = sb.length();
                sb.append(Card.yen(it.optLong(1)));
                Card.color(sb, b, ink2);
            }
        }
        if (sb.length() == 0) {
            sb.append(mo == null ? "アプリを開くと、今月の支出が出る。" : "今月の記録はまだない。");
            Card.color(sb, 0, ink3);
        }
        v.setTextViewText(R.id.w_body, sb);
        v.setTextColor(R.id.w_body, ink);

        v.setTextViewText(R.id.w_foot, "＋ 支出を入れる");
        v.setTextColor(R.id.w_foot, accent);
        v.setOnClickPendingIntent(R.id.w_foot, W.open(c, "spend", 42));
        v.setOnClickPendingIntent(R.id.root, W.open(c, "money", 41));
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
    <string name="widget_timeline_desc">いまの予定と次の予定（半透明）</string>
    <string name="widget_tasks_desc">残っているタスクと次の一歩（半透明）</string>
    <string name="widget_focus_desc">今日の集中時間と連続日数（半透明）</string>
    <string name="widget_money_desc">今月の支出と予算の残り</string>
</resources>
""")

w(RES + "/values/colors.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="app_bg">#F5F6F5</color>
</resources>
""")

# WebView は「アプリのテーマが明るいか暗いか」で端末のダークモードを判断する。
# 明るいテーマ（既定）と、夜用（values-night）の2つを用意して、端末の設定に合わせる。
w(RES + "/values/styles.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="AppTheme" parent="android:Theme.DeviceDefault.Light.NoActionBar">
        <item name="android:windowBackground">@color/app_bg</item>
        <item name="android:statusBarColor">@color/app_bg</item>
        <item name="android:navigationBarColor">@color/app_bg</item>
        <item name="android:windowLightStatusBar">true</item>
    </style>
</resources>
""")

w(RES + "/values-night/styles.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="AppTheme" parent="android:Theme.DeviceDefault.NoActionBar">
        <item name="android:windowBackground">@color/app_bg</item>
        <item name="android:statusBarColor">@color/app_bg</item>
        <item name="android:navigationBarColor">@color/app_bg</item>
        <item name="android:windowLightStatusBar">false</item>
    </style>
</resources>
""")

w(RES + "/values-night/colors.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="app_bg">#111314</color>
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

# DESK のウィジェットと同じ、壁紙が透ける半透明のカード
w(RES + "/drawable/w_glass.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#99101014" />
    <corners android:radius="24dp" />
    <stroke android:width="1dp" android:color="#1FFFFFFF" />
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

def widget_info(name, desc, w_dp, h_dp, cw, ch):
    w(RES + "/xml/%s_widget_info.xml" % name,
      '<?xml version="1.0" encoding="utf-8"?>\n'
      '<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"\n'
      '    android:description="@string/widget_%s_desc"\n'
      '    android:initialLayout="@layout/widget_card"\n'
      '    android:minWidth="%ddp"\n'
      '    android:minHeight="%ddp"\n'
      '    android:minResizeWidth="110dp"\n'
      '    android:minResizeHeight="110dp"\n'
      '    android:resizeMode="horizontal|vertical"\n'
      '    android:targetCellWidth="%d"\n'
      '    android:targetCellHeight="%d"\n'
      '    android:updatePeriodMillis="1800000"\n'
      '    android:widgetCategory="home_screen" />\n' % (desc, w_dp, h_dp, cw, ch))


widget_info("timeline", "timeline", 250, 110, 4, 3)
widget_info("tasks", "tasks", 180, 110, 3, 3)
widget_info("focus", "focus", 110, 110, 2, 2)
widget_info("money", "money", 180, 110, 3, 2)

w(RES + "/layout/widget_card.xml", r"""<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/root"
    android:layout_width="match_parent"
    android:layout_height="match_parent">

    <ImageView
        android:id="@+id/bg"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:scaleType="fitXY"
        android:src="@drawable/w_glass" />

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:orientation="vertical"
        android:padding="14dp">

        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:gravity="center_vertical"
            android:orientation="horizontal">

            <TextView
                android:id="@+id/w_label"
                android:layout_width="0dp"
                android:layout_height="wrap_content"
                android:layout_weight="1"
                android:maxLines="1"
                android:text="ConTodo"
                android:textSize="10sp"
                android:textStyle="bold" />

            <TextView
                android:id="@+id/w_right"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:maxLines="1"
                android:textSize="10sp" />
        </LinearLayout>

        <LinearLayout
            android:id="@+id/w_bigrow"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:gravity="bottom"
            android:orientation="horizontal"
            android:paddingTop="2dp">

            <TextView
                android:id="@+id/w_big"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:fontFamily="sans-serif-light"
                android:includeFontPadding="false"
                android:maxLines="1"
                android:textSize="32sp" />

            <TextView
                android:id="@+id/w_unit"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:paddingStart="4dp"
                android:paddingBottom="4dp"
                android:textSize="11sp" />
        </LinearLayout>

        <TextView
            android:id="@+id/w_body"
            android:layout_width="match_parent"
            android:layout_height="0dp"
            android:layout_weight="1"
            android:ellipsize="end"
            android:lineSpacingMultiplier="1.15"
            android:paddingTop="6dp"
            android:textSize="12sp" />

        <TextView
            android:id="@+id/w_foot"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:maxLines="1"
            android:paddingTop="4dp"
            android:textSize="10.5sp" />
    </LinearLayout>
</FrameLayout>
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

# ---------------------------------------------------------------- emulator test
w("emu.sh", r"""#!/bin/bash
# エミュレータ上で、インストール → 起動 → 画面撮影 までを試す
APK=app/build/outputs/apk/release/app-release.apk
{
  echo "=== device ==="
  adb shell getprop ro.build.version.release
  adb shell getprop ro.build.version.sdk
  echo "=== install ==="
  adb install -r "$APK" 2>&1
  echo "install exit: $?"
  adb shell pm list packages | grep contodo
  adb shell dumpsys package app.contodo | grep -E "versionName|versionCode|targetSdk|minSdk|flags=|signatures|Signing" | head -12
  echo "=== launch ==="
  adb shell monkey -p app.contodo -c android.intent.category.LAUNCHER 1 2>&1
} > emu.log 2>&1
sleep 30
adb exec-out screencap -p > shot-app.png
{
  echo "=== resumed activity ==="
  adb shell dumpsys activity activities | grep -iE "mResumedActivity|topResumedActivity" | head -3
  echo "=== widgets registered ==="
  adb shell dumpsys appwidget | grep -iE "contodo" | head -8
} >> emu.log 2>&1
adb logcat -d | grep -iE "AndroidRuntime|FATAL|app\.contodo|ConTodo|chromium.*(ERROR|Uncaught)" | tail -80 > crash.log
echo "emulator test done"
""")

print("project written")
