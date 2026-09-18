using BepInEx;
using BepInEx.Unity.IL2CPP;
using BepInEx.Logging;
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using Il2CppInterop.Runtime.Injection;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BrainBridge
{
    [BepInPlugin("com.brain.desktopmate.bridge", "Brain Desktop Mate Bridge", "2.0.0")]
    public class BrainBridgePlugin : BasePlugin
    {
        internal static new ManualLogSource Log;
        private TcpListener _tcpListener;
        private CancellationTokenSource _cts;
        private DesktopMateAdapter _adapter;
        private int _activeConnections = 0;

        private const int MAX_CONNECTIONS = 2;
        private const int MAX_MESSAGE_SIZE = 8192;
        private const string PROTOCOL_NAME = "brain-desktopmate";
        private const int PROTOCOL_VERSION = 1;

        public override void Load()
        {
            Log = base.Log;
            Log.LogInfo("BrainBridge v2.0.0 loading...");

            try
            {
                HarmonyLib.Harmony.CreateAndPatchAll(typeof(UWC_Patch));
                Log.LogInfo("Harmony patches applied.");
            }
            catch (Exception e)
            {
                Log.LogError($"Error applying Harmony patches: {e}");
            }

            try
            {
                ClassInjector.RegisterTypeInIl2Cpp<UnityMainThreadDispatcher>();
                AddComponent<UnityMainThreadDispatcher>();
                Log.LogInfo("UnityMainThreadDispatcher registered and added");
            }
            catch (Exception ex)
            {
                Log.LogError($"Failed to register UnityMainThreadDispatcher: {ex}");
            }

            try
            {
                UnityEngine.Application.runInBackground = true;
                UnityEngine.Application.targetFrameRate = 30;
                Log.LogInfo("Application.runInBackground set to true, targetFrameRate set to 30 FPS");
            }
            catch (Exception ex)
            {
                Log.LogWarning($"Could not set Application properties: {ex.Message}");
            }

            _adapter = new DesktopMateAdapter();
            _cts = new CancellationTokenSource();
            Task.Run(() => StartServer(_cts.Token));

            Log.LogInfo("BrainBridge loaded. Pure managed WebSocket server starting on ws://127.0.0.1:8766/");
        }

        private async Task StartServer(CancellationToken token)
        {
            try
            {
                // Pure managed TcpListener — 100% Wine / CoreCLR compatible, zero native websocket.dll dependencies
                _tcpListener = new TcpListener(IPAddress.Loopback, 8766);
                _tcpListener.Server.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
                _tcpListener.Start();
                Log.LogInfo("WebSocket server listening on ws://127.0.0.1:8766/");

                while (!token.IsCancellationRequested)
                {
                    var client = await _tcpListener.AcceptTcpClientAsync();
                    if (_activeConnections >= MAX_CONNECTIONS)
                    {
                        client.Close();
                        continue;
                    }
                    _ = HandleClient(client, token);
                }
            }
            catch (Exception ex)
            {
                if (!token.IsCancellationRequested)
                {
                    Log.LogError($"Server error: {ex}");
                }
            }
        }

        private async Task HandleClient(TcpClient client, CancellationToken token)
        {
            Interlocked.Increment(ref _activeConnections);
            try
            {
                using (client)
                using (var stream = client.GetStream())
                {
                    // 1. Perform HTTP WebSocket Upgrade Handshake
                    if (!await PerformHandshake(stream, token))
                    {
                        return;
                    }

                    Log.LogInfo("Brain client connected via WebSocket");

                    // 2. Read WebSocket frames
                    while (!token.IsCancellationRequested && client.Connected)
                    {
                        var msg = await ReadWebSocketFrame(stream, token);
                        if (msg == null)
                        {
                            break; // Connection closed or close frame
                        }

                        if (msg.Length == 0)
                        {
                            continue; // Control frame handled
                        }

                        if (msg.Length > MAX_MESSAGE_SIZE)
                        {
                            await SendResponse(stream, MakeError("unknown", "unknown",
                                "OVERSIZED_MESSAGE", "Message exceeds 8KB limit"));
                            continue;
                        }

                        string raw = Encoding.UTF8.GetString(msg);
                        try
                        {
                            await ProcessMessage(stream, raw);
                        }
                        catch (Exception pex)
                        {
                            Log.LogError($"Error in ProcessMessage: {pex}");
                        }
                    }
                }
            }
            catch (Exception e)
            {
                Log.LogInfo($"WebSocket client session ended: {e.Message}");
            }
            finally
            {
                Interlocked.Decrement(ref _activeConnections);
                Log.LogInfo("Brain client disconnected");
            }
        }

        private async Task<bool> PerformHandshake(NetworkStream stream, CancellationToken token)
        {
            byte[] buffer = new byte[4096];
            int read = await stream.ReadAsync(buffer, 0, buffer.Length, token);
            if (read <= 0) return false;

            string request = Encoding.UTF8.GetString(buffer, 0, read);
            string secKey = null;

            using (var reader = new StringReader(request))
            {
                string line;
                while ((line = reader.ReadLine()) != null)
                {
                    if (line.StartsWith("Sec-WebSocket-Key:", StringComparison.OrdinalIgnoreCase))
                    {
                        secKey = line.Substring("Sec-WebSocket-Key:".Length).Trim();
                        break;
                    }
                }
            }

            if (string.IsNullOrEmpty(secKey))
            {
                byte[] badReq = Encoding.UTF8.GetBytes("HTTP/1.1 400 Bad Request\r\n\r\n");
                await stream.WriteAsync(badReq, 0, badReq.Length, token);
                return false;
            }

            // Compute RFC 6455 accept key
            string acceptKey;
            using (var sha1 = SHA1.Create())
            {
                byte[] hash = sha1.ComputeHash(Encoding.UTF8.GetBytes(secKey + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"));
                acceptKey = Convert.ToBase64String(hash);
            }

            string response = "HTTP/1.1 101 Switching Protocols\r\n" +
                              "Upgrade: websocket\r\n" +
                              "Connection: Upgrade\r\n" +
                              $"Sec-WebSocket-Accept: {acceptKey}\r\n\r\n";

            byte[] respBytes = Encoding.UTF8.GetBytes(response);
            await stream.WriteAsync(respBytes, 0, respBytes.Length, token);
            return true;
        }

        private async Task<byte[]> ReadWebSocketFrame(NetworkStream stream, CancellationToken token)
        {
            byte[] header = new byte[2];
            if (!await ReadExact(stream, header, 0, 2, token)) return null;

            int opcode = header[0] & 0x0F;
            if (opcode == 8) return null; // Close frame

            bool isMasked = (header[1] & 0x80) != 0;
            ulong len = (ulong)(header[1] & 0x7F);

            if (len == 126)
            {
                byte[] extLen = new byte[2];
                if (!await ReadExact(stream, extLen, 0, 2, token)) return null;
                len = (ulong)((extLen[0] << 8) | extLen[1]);
            }
            else if (len == 127)
            {
                byte[] extLen = new byte[8];
                if (!await ReadExact(stream, extLen, 0, 8, token)) return null;
                len = 0;
                for (int i = 0; i < 8; i++) len = (len << 8) | extLen[i];
            }

            if (len > MAX_MESSAGE_SIZE)
            {
                return new byte[MAX_MESSAGE_SIZE + 1]; // Signal oversized
            }

            byte[] mask = new byte[4];
            if (isMasked)
            {
                if (!await ReadExact(stream, mask, 0, 4, token)) return null;
            }

            byte[] payload = new byte[(int)len];
            if (!await ReadExact(stream, payload, 0, (int)len, token)) return null;

            if (isMasked)
            {
                for (int i = 0; i < payload.Length; i++)
                {
                    payload[i] ^= mask[i % 4];
                }
            }

            if (opcode == 9) // Ping from client
            {
                byte[] pong = new byte[2 + payload.Length];
                pong[0] = 0x8A; // FIN + Pong
                pong[1] = (byte)payload.Length;
                Buffer.BlockCopy(payload, 0, pong, 2, payload.Length);
                await stream.WriteAsync(pong, 0, pong.Length, token);
                await stream.FlushAsync(token);
                return Array.Empty<byte>(); // Handled control frame
            }

            return payload;
        }

        private async Task<bool> ReadExact(NetworkStream stream, byte[] buffer, int offset, int count, CancellationToken token)
        {
            int total = 0;
            while (total < count)
            {
                int read = await stream.ReadAsync(buffer, offset + total, count - total, token);
                if (read <= 0) return false;
                total += read;
            }
            return true;
        }

        private async Task ProcessMessage(NetworkStream stream, string raw)
        {
            JsonObject msg;
            try
            {
                msg = JsonNode.Parse(raw) as JsonObject;
                if (msg == null) throw new FormatException("Root must be a JSON object");
            }
            catch
            {
                await SendResponse(stream, MakeError("unknown", "unknown",
                    "INVALID_JSON", "Message is not valid JSON"));
                return;
            }

            // Safe protocol validation
            string proto = msg["protocol"]?.ToString();
            string verStr = msg["version"]?.ToString();
            string reqId = msg["request_id"]?.ToString() ?? msg["id"]?.ToString() ?? "unknown";
            string action = msg["action"]?.ToString() ?? "unknown";

            if (proto != PROTOCOL_NAME || verStr != PROTOCOL_VERSION.ToString())
            {
                await SendResponse(stream, MakeError(reqId, action,
                    "PROTOCOL_MISMATCH",
                    $"Expected protocol={PROTOCOL_NAME} v{PROTOCOL_VERSION}, got {proto} v{verStr}"));
                return;
            }

            if (string.IsNullOrEmpty(action) || action == "unknown")
            {
                await SendResponse(stream, MakeError(reqId, action,
                    "MALFORMED_REQUEST", "Missing 'action' field"));
                return;
            }

            var args = (msg["arguments"] as JsonObject) ?? (msg["payload"] as JsonObject) ?? new JsonObject();

            // Dispatch action
            var response = await HandleAction(action, reqId, args);
            await SendResponse(stream, response);
        }

        private async Task<JsonObject> HandleAction(string action, string reqId, JsonObject payload)
        {
            try
            {
                switch (action.ToLowerInvariant())
                {
                    case "ping":
                        return MakeSuccess(reqId, action, new JsonObject
                        {
                            ["pong"] = true,
                            ["timestamp"] = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
                        }, "verified");

                    case "health":
                        var status = await UnityMainThreadDispatcher.EnqueueAsync(() => _adapter.CheckRuntime());
                        return MakeSuccess(reqId, action, new JsonObject
                        {
                            ["runtime_ready"] = status.runtimeReady,
                            ["character_ready"] = status.characterReady,
                            ["details"] = status.details
                        }, status.runtimeReady ? "verified" : "unavailable");

                    case "capabilities":
                        var caps = await UnityMainThreadDispatcher.EnqueueAsync(() => _adapter.GetCapabilities());
                        var capsObj = new JsonObject();
                        foreach (var kv in caps)
                        {
                            if (kv.Value is Dictionary<string, string> dict)
                            {
                                var inner = new JsonObject();
                                foreach (var ikv in dict) inner[ikv.Key] = ikv.Value;
                                capsObj[kv.Key] = inner;
                            }
                        }
                        return MakeSuccess(reqId, action, new JsonObject
                        {
                            ["capabilities"] = capsObj
                        }, "verified");

                    case "emotion":
                    case "set_emotion":
                        string emotion = payload["name"]?.ToString() ?? payload["emotion"]?.ToString();
                        if (string.IsNullOrEmpty(emotion))
                            return MakeError(reqId, action, "MISSING_PARAM", "Missing 'emotion' or 'name' in arguments");

                        var emoResult = await UnityMainThreadDispatcher.EnqueueAsync(() => _adapter.SetEmotion(emotion));
                        return emoResult.success
                            ? MakeSuccess(reqId, action, new JsonObject { ["emotion"] = emotion }, emoResult.status)
                            : MakeError(reqId, action, emoResult.status.ToUpper(), emoResult.error);

                    case "animation":
                    case "play_animation":
                        string anim = payload["name"]?.ToString() ?? payload["animation"]?.ToString();
                        if (string.IsNullOrEmpty(anim))
                            return MakeError(reqId, action, "MISSING_PARAM", "Missing 'name' or 'animation' in arguments");

                        var animResult = await _adapter.PlayAnimationAsync(anim);
                        if (animResult.success)
                        {
                            var dataObj = new JsonObject();
                            if (animResult.data != null)
                            {
                                foreach (var kv in animResult.data) dataObj[kv.Key] = kv.Value?.ToString();
                            }
                            return MakeSuccess(reqId, action, dataObj, animResult.status);
                        }
                        return MakeError(reqId, action, animResult.status.ToUpper(), animResult.error);

                    case "look_at":
                        string target = payload["target"]?.ToString();
                        if (string.IsNullOrEmpty(target))
                            return MakeError(reqId, action, "MISSING_PARAM", "Missing 'target' in arguments");

                        var lookResult = await UnityMainThreadDispatcher.EnqueueAsync(() => _adapter.LookAt(target));
                        return lookResult.success
                            ? MakeSuccess(reqId, action, new JsonObject { ["target"] = target }, lookResult.status)
                            : MakeError(reqId, action, lookResult.status.ToUpper(), lookResult.error);

                    case "voice":
                    case "play_voice":
                        string filePath = payload["file_path"]?.ToString() ?? payload["file"]?.ToString();
                        if (string.IsNullOrEmpty(filePath))
                            return MakeError(reqId, action, "MISSING_PARAM", "Missing 'file_path' or 'file' in arguments");

                        var voiceResult = _adapter.PlayVoice(filePath);
                        return voiceResult.success
                            ? MakeSuccess(reqId, action, new JsonObject { ["file_path"] = filePath }, voiceResult.status)
                            : MakeError(reqId, action, voiceResult.status.ToUpper(), voiceResult.error);

                    case "character_state":
                    case "get_character_state":
                        var stateResult = await UnityMainThreadDispatcher.EnqueueAsync(() => _adapter.GetCharacterState());
                        return stateResult.success
                            ? MakeSuccess(reqId, action, new JsonObject(), stateResult.status)
                            : MakeError(reqId, action, stateResult.status.ToUpper(), stateResult.error);

                    case "trim_memory":
                    case "trim":
                        var trimResult = await UnityMainThreadDispatcher.EnqueueAsync(() => _adapter.TrimMemory());
                        return trimResult.success
                            ? MakeSuccess(reqId, action, new JsonObject(), trimResult.status)
                            : MakeError(reqId, action, trimResult.status.ToUpper(), trimResult.error);

                    case "set_fps":
                    case "target_fps":
                        int targetFps = 30;
                        if (payload["fps"] != null && int.TryParse(payload["fps"].ToString(), out int parsedFps))
                        {
                            targetFps = parsedFps;
                        }
                        var fpsResult = await UnityMainThreadDispatcher.EnqueueAsync(() => _adapter.SetFps(targetFps));
                        return fpsResult.success
                            ? MakeSuccess(reqId, action, new JsonObject { ["target_fps"] = targetFps }, fpsResult.status)
                            : MakeError(reqId, action, fpsResult.status.ToUpper(), fpsResult.error);

                    default:
                        return MakeError(reqId, action, "UNKNOWN_ACTION",
                            $"Action '{action}' is not supported by this bridge");
                }
            }
            catch (Exception ex)
            {
                Log.LogError($"Error in HandleAction({action}): {ex}");
                return MakeError(reqId, action, "INTERNAL_ERROR", ex.Message);
            }
        }

        private JsonObject MakeSuccess(string reqId, string action, JsonObject data, string status = "verified")
        {
            return new JsonObject
            {
                ["protocol"] = PROTOCOL_NAME,
                ["version"] = PROTOCOL_VERSION,
                ["request_id"] = reqId,
                ["action"] = action,
                ["success"] = true,
                ["status"] = status,
                ["data"] = data,
                ["error"] = null
            };
        }

        private JsonObject MakeError(string reqId, string action, string code, string message)
        {
            return new JsonObject
            {
                ["protocol"] = PROTOCOL_NAME,
                ["version"] = PROTOCOL_VERSION,
                ["request_id"] = reqId,
                ["action"] = action,
                ["success"] = false,
                ["status"] = "failed",
                ["data"] = null,
                ["error"] = new JsonObject
                {
                    ["code"] = code,
                    ["message"] = message
                }
            };
        }

        private async Task SendResponse(NetworkStream stream, JsonObject response)
        {
            string json = response.ToJsonString();
            byte[] payload = Encoding.UTF8.GetBytes(json);
            if (payload.Length > MAX_MESSAGE_SIZE)
            {
                Log.LogWarning("Response exceeds max size, truncating");
                return;
            }

            // Server-to-client WebSocket frame (unmasked)
            byte[] frame;
            if (payload.Length <= 125)
            {
                frame = new byte[2 + payload.Length];
                frame[0] = 0x81; // FIN + text
                frame[1] = (byte)payload.Length;
                Buffer.BlockCopy(payload, 0, frame, 2, payload.Length);
            }
            else
            {
                frame = new byte[4 + payload.Length];
                frame[0] = 0x81; // FIN + text
                frame[1] = 126;  // 16-bit length follows
                frame[2] = (byte)((payload.Length >> 8) & 0xFF);
                frame[3] = (byte)(payload.Length & 0xFF);
                Buffer.BlockCopy(payload, 0, frame, 4, payload.Length);
            }

            await stream.WriteAsync(frame, 0, frame.Length);
            await stream.FlushAsync();
        }

        public override bool Unload()
        {
            _cts?.Cancel();
            try { _tcpListener?.Stop(); } catch {}
            return base.Unload();
        }
    }
}
