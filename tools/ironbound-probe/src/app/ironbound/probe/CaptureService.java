package app.ironbound.probe;

import android.app.Service;
import android.content.ComponentName;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.Binder;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.Parcel;
import android.os.RemoteException;
import android.os.SystemClock;
import org.json.JSONObject;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;

/** Observation-only diagnostic. No resistance, rack, reservation or firmware API. */
public final class CaptureService extends Service {
    private static final String SERVICE = "com.riptlabs.common.mcb.IRiptMcbService";
    private static final String LISTENER = "com.riptlabs.common.mcb.IRiptMcbServiceListener";
    private final Handler main = new Handler(Looper.getMainLooper());
    private BufferedWriter output;
    private IBinder remote;
    private boolean bound;
    private boolean registered;
    private boolean started;
    private boolean finished;
    private int count;
    private long bytes;
    private static final long MAX_BYTES = 8 * 1024 * 1024;

    private final Binder listener = new Binder() {
        @Override protected boolean onTransact(int code, Parcel data, Parcel reply, int flags)
                throws RemoteException {
            if (code == INTERFACE_TRANSACTION) {
                if (reply != null) reply.writeString(LISTENER);
                return true;
            }
            if (code == 1 || code == 2) {
                data.enforceInterface(LISTENER);
                if (code == 1) {
                    record("status", data.readInt());
                } else {
                    String raw = data.readString();
                    Object payload = raw;
                    try { payload = new JSONObject(raw); } catch (Exception ignored) { }
                    record("message", payload);
                }
                return true;
            }
            return super.onTransact(code, data, reply, flags);
        }
    };

    private final ServiceConnection connection = new ServiceConnection() {
        @Override public void onServiceConnected(ComponentName name, IBinder binder) {
            if (finished) return;
            remote = binder;
            record("connected", name.flattenToShortString());
            try {
                if (!SERVICE.equals(binder.getInterfaceDescriptor())) {
                    throw new IllegalStateException("Unexpected Binder descriptor");
                }
                record("state", transact(2));
                // Set before transaction so cleanup attempts unregister even on reply failure.
                registered = true;
                transact(7);
                record("registered", true);
            } catch (Exception e) {
                record("error", e.toString());
                finishCapture("registration_failed");
            }
        }
        @Override public void onServiceDisconnected(ComponentName name) {
            record("disconnected", name.flattenToShortString());
            remote = null;
            finishCapture("service_disconnected");
        }
    };

    /** Deliberately allow only getState, add-named-listener and remove-listener. */
    private int transact(int code) throws RemoteException {
        if (code != 2 && code != 5 && code != 7) {
            throw new IllegalArgumentException("Observation-only transaction allowlist");
        }
        if (remote == null) throw new RemoteException("Service unavailable");
        Parcel data = Parcel.obtain();
        Parcel reply = Parcel.obtain();
        try {
            data.writeInterfaceToken(SERVICE);
            if (code == 5 || code == 7) data.writeStrongBinder(listener);
            if (code == 7) data.writeString(getPackageName());
            if (!remote.transact(code, data, reply, 0)) {
                throw new RemoteException("Unsupported transaction " + code);
            }
            reply.readException();
            return code == 2 ? reply.readInt() : 0;
        } finally {
            data.recycle();
            reply.recycle();
        }
    }

    private synchronized void record(String kind, Object value) {
        if (output == null) return;
        try {
            JSONObject row = new JSONObject();
            row.put("kind", kind);
            row.put("received_elapsed_ms", SystemClock.elapsedRealtime());
            row.put("received_epoch_ms", System.currentTimeMillis());
            row.put("value", value == null ? JSONObject.NULL : value);
            String line = row.toString();
            output.write(line);
            output.newLine();
            output.flush();
            bytes += line.getBytes(StandardCharsets.UTF_8).length + 1;
            if ("message".equals(kind)) count++;
            if (bytes >= MAX_BYTES && !finished) postFinish("size_limit", 0);
        } catch (Exception e) {
            postFinish("write_failed", 0);
        }
    }

    private void postFinish(final String reason, long delayMillis) {
        main.postDelayed(new Runnable() {
            @Override public void run() { finishCapture(reason); }
        }, delayMillis);
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (started) return START_NOT_STICKY;
        started = true;
        int seconds = Math.max(5, Math.min(60, intent == null ? 20 : intent.getIntExtra("seconds", 20)));
        try {
            File file = new File(getFilesDir(), "capture-" + System.currentTimeMillis() + ".jsonl");
            output = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(file), StandardCharsets.UTF_8));
            record("capture_started", "seconds=" + seconds + "; observer_uid=" + android.os.Process.myUid());
            Intent serviceIntent = new Intent().setComponent(new ComponentName(
                    "com.riptlabs.mcb.service", "com.riptlabs.common.mcb.RiptMcbService"));
            bound = bindService(serviceIntent, connection, BIND_AUTO_CREATE);
            record("bind_requested", bound);
            if (!bound) finishCapture("bind_failed");
            else postFinish("duration_elapsed", seconds * 1000L);
        } catch (Exception e) {
            record("error", e.toString());
            finishCapture("start_failed");
        }
        return START_NOT_STICKY;
    }

    private void finishCapture(String reason) {
        if (finished) return;
        finished = true;
        main.removeCallbacksAndMessages(null);
        if (registered && remote != null) {
            try { transact(5); record("unregistered", true); }
            catch (Exception e) { record("cleanup_error", e.toString()); }
        }
        if (bound) {
            try { unbindService(connection); record("unbound", true); }
            catch (Exception e) { record("cleanup_error", e.toString()); }
        }
        record("capture_finished", reason + "; messages=" + count);
        synchronized (this) {
            try { if (output != null) output.close(); } catch (Exception ignored) { }
            output = null;
        }
        stopSelf();
    }

    @Override public void onDestroy() { finishCapture("service_destroyed"); super.onDestroy(); }
    @Override public IBinder onBind(Intent intent) { return null; }
}
