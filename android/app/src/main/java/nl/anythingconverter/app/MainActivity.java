package nl.anythingconverter.app;

import android.app.Activity;
import android.content.ClipData;
import android.content.ContentValues;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.OutputStream;

/**
 * Anything Converter voor Android: toont de web-app en voegt twee dingen toe die een
 * WebView zelf niet kan: bestanden kiezen via Android en resultaten opslaan in Downloads.
 */
public class MainActivity extends Activity {
    private static final String HOME = "https://wikidave.github.io/The-Anything-Converter/";
    private static final String HOST = "wikidave.github.io";
    private static final int PICK_FILES = 1;

    private WebView web;
    private ValueCallback<Uri[]> pendingPick;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.BLACK);
        getWindow().setNavigationBarColor(Color.BLACK);

        web = new WebView(this);
        web.setBackgroundColor(Color.BLACK);
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setUserAgentString(s.getUserAgentString() + " AnythingConverterApp/" + BuildConfigHolder.VERSION);

        web.addJavascriptInterface(new SaveBridge(), "AnythingAndroid");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                if (HOST.equals(u.getHost())) return false;
                // Andere sites (zoals GitHub-downloads) openen in de browser
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignored) { }
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) {
                    view.loadDataWithBaseURL(null, OFFLINE_PAGE, "text/html", "utf-8", null);
                }
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (pendingPick != null) pendingPick.onReceiveValue(null);
                pendingPick = callback;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE);
                try {
                    startActivityForResult(Intent.createChooser(i, "Kies bestanden"), PICK_FILES);
                } catch (Exception e) {
                    pendingPick = null;
                    return false;
                }
                return true;
            }
        });

        if (state != null) web.restoreState(state);
        else web.loadUrl(HOME);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != PICK_FILES || pendingPick == null) return;
        Uri[] result = null;
        if (resultCode == RESULT_OK && data != null) {
            ClipData clip = data.getClipData();
            if (clip != null) {
                result = new Uri[clip.getItemCount()];
                for (int i = 0; i < clip.getItemCount(); i++) result[i] = clip.getItemAt(i).getUri();
            } else if (data.getData() != null) {
                result = new Uri[]{data.getData()};
            }
        }
        pendingPick.onReceiveValue(result);
        pendingPick = null;
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    /** Ontvangt bestanden van de pagina in stukjes (base64) en schrijft ze naar Downloads/Anything Converter. */
    private class SaveBridge {
        private OutputStream out;
        private Uri uri;
        private String name;

        @JavascriptInterface
        public boolean begin(String fileName, String mime) {
            try {
                ContentValues v = new ContentValues();
                v.put(MediaStore.Downloads.DISPLAY_NAME, fileName);
                v.put(MediaStore.Downloads.MIME_TYPE, mime == null || mime.isEmpty() ? "application/octet-stream" : mime);
                v.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/Anything Converter");
                v.put(MediaStore.Downloads.IS_PENDING, 1);
                uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
                out = getContentResolver().openOutputStream(uri);
                name = fileName;
                return out != null;
            } catch (Exception e) {
                return false;
            }
        }

        @JavascriptInterface
        public boolean chunk(String b64) {
            try {
                out.write(Base64.decode(b64, Base64.DEFAULT));
                return true;
            } catch (Exception e) {
                return false;
            }
        }

        @JavascriptInterface
        public boolean end() {
            try {
                out.close();
                ContentValues v = new ContentValues();
                v.put(MediaStore.Downloads.IS_PENDING, 0);
                getContentResolver().update(uri, v, null, null);
                final String msg = "Opgeslagen in Downloads/Anything Converter: " + name;
                runOnUiThread(() -> Toast.makeText(MainActivity.this, msg, Toast.LENGTH_LONG).show());
                return true;
            } catch (Exception e) {
                return false;
            }
        }
    }

    private static final String OFFLINE_PAGE =
        "<html><body style='background:#000;color:#a6ff5c;font-family:monospace;padding:24px'>"
        + "<pre>┌───────────────────────────────┐\n│  GEEN INTERNETVERBINDING      │\n│  de converter heeft internet  │\n│  nodig. probeer het opnieuw.  │\n└───────────────────────────────┘</pre>"
        + "<a style='color:#d9ffb8' href='" + HOME + "'>[ OPNIEUW PROBEREN ]</a></body></html>";

    /** Versienummer voor de user-agent, zonder BuildConfig (die staat in AGP 8 standaard uit). */
    private static final class BuildConfigHolder {
        static final String VERSION = "2.1";
    }
}
