using System;
using System.Reflection;
using System.Linq;
namespace InspectTool {
    class Program {
        static void Main() {
            var asm = Assembly.LoadFrom("../../desktopmate/Desktop Mate/BepInEx/interop/Unity.UniWindowController.dll");
            var t = asm.GetExportedTypes().FirstOrDefault(x => x.Name == "UniWindowController");
            if (t != null) {
                Console.WriteLine("Base type: " + t.BaseType.FullName);
            }
        }
    }
}
