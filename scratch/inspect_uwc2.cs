using System;
using System.Reflection;
using System.Linq;

class InspectUWC2 {
    static void Main() {
        var asm = Assembly.LoadFrom("../../desktopmate/Desktop Mate/BepInEx/interop/Unity.UniWindowController.dll");
        var t = asm.GetExportedTypes().FirstOrDefault(x => x.Name == "UniWindowController");
        if (t != null) {
            foreach (var m in t.GetMethods()) {
                if (m.Name.Contains("SetTransparentType") || m.Name.Contains("Transparent")) {
                    Console.WriteLine("Method: " + m.Name);
                    foreach (var p in m.GetParameters()) Console.WriteLine("  Param: " + p.ParameterType.Name);
                }
            }
        }
    }
}
