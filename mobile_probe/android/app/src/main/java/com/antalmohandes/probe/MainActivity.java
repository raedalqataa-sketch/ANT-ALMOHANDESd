package com.antalmohandes.probe;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import androidx.webkit.WebViewAssetLoader;
import java.io.ByteArrayInputStream;
import java.io.OutputStream;

/** Offline feasibility only. Not the full design studio or a production release. */
public class MainActivity extends Activity {
    private static final int SAVE_DOCUMENT = 10;
    private WebView web;
    private byte[] pendingFile;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        web = new WebView(this);
        setContentView(web);
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(true);
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(false);
        WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this)).build();
        web.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
                WebResourceResponse local = loader.shouldInterceptRequest(req.getUrl());
                return local != null ? local : new WebResourceResponse("text/plain", "UTF-8", 403, "Local assets only", java.util.Collections.emptyMap(), new ByteArrayInputStream(new byte[0]));
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                return !"appassets.androidplatform.net".equals(req.getUrl().getHost());
            }
        });
        web.addJavascriptInterface(new FileBridge(), "AndroidFiles");
        web.loadUrl("https://appassets.androidplatform.net/assets/index.html");
    }

    private final class FileBridge {
        @JavascriptInterface public void save(String name, String encoded) {
            if (name == null || !name.matches("[a-z_]+(?:-(?:GF|FF))?\\.(?:svg|pdf|dxf|json)") || encoded == null || encoded.length() > 30_000_000) return;
            final byte[] bytes;
            try { bytes = Base64.decode(encoded, Base64.DEFAULT); } catch (IllegalArgumentException e) { return; }
            runOnUiThread(() -> {
                if (pendingFile != null) { Toast.makeText(MainActivity.this, "أكمل حفظ الملف الحالي أولًا", Toast.LENGTH_SHORT).show(); return; }
                pendingFile = bytes;
                Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType(name.endsWith(".pdf") ? "application/pdf" : "application/octet-stream");
                intent.putExtra(Intent.EXTRA_TITLE, name);
                try { startActivityForResult(intent, SAVE_DOCUMENT); }
                catch (android.content.ActivityNotFoundException e) { pendingFile = null; Toast.makeText(MainActivity.this, "لا يتوفر منتقي ملفات", Toast.LENGTH_LONG).show(); }
            });
        }
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != SAVE_DOCUMENT) return;
        final byte[] bytes = pendingFile; pendingFile = null;
        if (result != RESULT_OK || data == null || data.getData() == null || bytes == null) return;
        Uri destination = data.getData();
        new Thread(() -> {
            try (OutputStream stream = getContentResolver().openOutputStream(destination)) {
                if (stream == null) throw new java.io.IOException("No output stream");
                stream.write(bytes);
                runOnUiThread(() -> Toast.makeText(this, "تم حفظ الملف", Toast.LENGTH_SHORT).show());
            } catch (Exception e) { runOnUiThread(() -> Toast.makeText(this, "تعذر حفظ الملف", Toast.LENGTH_LONG).show()); }
        }, "save-generated-plan").start();
    }

    @Override protected void onDestroy() { if (web != null) { web.removeJavascriptInterface("AndroidFiles"); web.destroy(); } super.onDestroy(); }
}
