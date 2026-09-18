using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;
using HarmonyLib;

namespace BrainBridge
{
    [HarmonyPatch]
    public class UWC_Patch
    {
        // Try to patch the EnableTransparent or set_isTransparent method
        [HarmonyPatch("Kirurobo.UniWindowController", "set_isTransparent")]
        [HarmonyPostfix]
        public static void Postfix_set_isTransparent(object __instance, bool value)
        {
            BrainBridgePlugin.Log?.LogInfo($"UWC set_isTransparent called with: {value}");
        }
        
        [HarmonyPatch("Kirurobo.UniWindowController", "Awake")]
        [HarmonyPostfix]
        public static void Postfix_Awake(object __instance)
        {
            BrainBridgePlugin.Log?.LogInfo("UWC Awake called!");
            try {
                var type = __instance.GetType();
                var prop = type.GetProperty("isTransparent");
                if (prop != null) {
                    prop.SetValue(__instance, true, null);
                    BrainBridgePlugin.Log?.LogInfo("Forced isTransparent to true in Awake");
                }
            } catch (Exception e) {
                BrainBridgePlugin.Log?.LogError($"Error in UWC Awake patch: {e}");
            }
        }
    }

    /// <summary>
    /// Unity MonoBehaviour registered in IL2CPP via ClassInjector.
    /// Drains actions queued from background socket threads during Unity's Update() loop
    /// and manages frame watcher callbacks for multi-frame runtime observation.
    /// </summary>
    public class UnityMainThreadDispatcher : MonoBehaviour
    {
        private static readonly ConcurrentQueue<Action> _queue = new ConcurrentQueue<Action>();
        private static readonly List<Action> _frameWatchers = new List<Action>();
        public static UnityMainThreadDispatcher Instance { get; private set; }

        public UnityMainThreadDispatcher(IntPtr ptr) : base(ptr) { }

        private void Awake()
        {
            Instance = this;
        }
        
        private bool _transparencyApplied = false;

        public static void Enqueue(Action action)
        {
            if (action != null)
            {
                _queue.Enqueue(action);
            }
        }

        public static void RegisterFrameWatcher(Action callback)
        {
            Enqueue(() =>
            {
                if (callback != null && !_frameWatchers.Contains(callback))
                {
                    _frameWatchers.Add(callback);
                }
            });
        }

        public static void UnregisterFrameWatcher(Action callback)
        {
            Enqueue(() =>
            {
                if (callback != null)
                {
                    _frameWatchers.Remove(callback);
                }
            });
        }

        public static Task<T> EnqueueAsync<T>(Func<T> func)
        {
            var tcs = new TaskCompletionSource<T>();
            _queue.Enqueue(() =>
            {
                try
                {
                    var result = func();
                    tcs.SetResult(result);
                }
                catch (Exception ex)
                {
                    tcs.SetException(ex);
                }
            });
            return tcs.Task;
        }

        private void Update()
        {
            if (!_transparencyApplied)
            {
                bool cameraSet = false;
                bool uwcSet = false;
                
                try {
                    // Try to enable transparency using Kirurobo.UniWindowController if it exists
                    var uwcType = Il2CppSystem.Type.GetType("Kirurobo.UniWindowController, Unity.UniWindowController");
                    if (uwcType != null) {
                        var uwcObjects = UnityEngine.Object.FindObjectsOfType(uwcType);
                        if (uwcObjects != null && uwcObjects.Length > 0) {
                            foreach (var obj in uwcObjects) {
                                var prop = uwcType.GetProperty("isTransparent");
                                if (prop != null) {
                                    prop.SetValue(obj, true, null);
                                    BrainBridgePlugin.Log?.LogInfo("Applied isTransparent via Il2CppSystem.Type");
                                    uwcSet = true;
                                }
                                var propTop = uwcType.GetProperty("isTopmost");
                                if (propTop != null) {
                                    propTop.SetValue(obj, true, null);
                                }
                            }
                        }
                    }
                    
                    // Also explicitly clear camera background
                    var cams = UnityEngine.Camera.allCameras;
                    if (cams != null && cams.Length > 0) {
                        foreach (var cam in cams) {
                            cam.clearFlags = UnityEngine.CameraClearFlags.SolidColor;
                            cam.backgroundColor = new UnityEngine.Color(0, 0, 0, 0);
                        }
                        BrainBridgePlugin.Log?.LogInfo("Set Camera background to transparent for all cameras");
                        cameraSet = true;
                    }
                    
                    if (cameraSet || uwcSet) {
                        _transparencyApplied = true;
                    }
                } catch (Exception e) {
                    BrainBridgePlugin.Log?.LogError($"Error in transparency block: {e}");
                }
            }

            while (_queue.TryDequeue(out var action))
            {
                try
                {
                    action();
                }
                catch (Exception ex)
                {
                    BrainBridgePlugin.Log?.LogError($"Error in UnityMainThreadDispatcher Action: {ex}");
                }
            }

            if (_frameWatchers.Count > 0)
            {
                var copy = _frameWatchers.ToArray();
                foreach (var watcher in copy)
                {
                    try
                    {
                        watcher();
                    }
                    catch (Exception ex)
                    {
                        BrainBridgePlugin.Log?.LogError($"Error in UnityMainThreadDispatcher FrameWatcher: {ex}");
                    }
                }
            }
        }
    }
}
