using System;
using System.IO;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;

class Program
{
    static void Main(string[] args)
    {
        string file = "/home/jai/Downloads/Brain/desktopmate/Desktop Mate/BepInEx/interop/Assembly-CSharp.dll";
        using var fs = File.OpenRead(file);
        using var pe = new PEReader(fs);
        var reader = pe.GetMetadataReader();
        foreach (var h in reader.TypeDefinitions)
        {
            var t = reader.GetTypeDefinition(h);
            string name = reader.GetString(t.Name);
            if (name == "MainManager")
            {
                Console.WriteLine($"=== TYPE: {name} ===");
                foreach (var m in t.GetMethods())
                {
                    var method = reader.GetMethodDefinition(m);
                    string mName = reader.GetString(method.Name);
                    if (mName == "SetExpression" || mName == "PlayAnim" || mName == "get_vrmInstance" || mName == "get_instance" || mName == "Instance")
                    {
                        Console.WriteLine($"  METHOD: {mName} (Signature token: {method.Signature})");
                        foreach (var paramHandle in method.GetParameters())
                        {
                            var param = reader.GetParameter(paramHandle);
                            Console.WriteLine($"    PARAM: {reader.GetString(param.Name)} (seq: {param.SequenceNumber})");
                        }
                    }
                }
                foreach (var f in t.GetFields())
                {
                    var field = reader.GetFieldDefinition(f);
                    string fName = reader.GetString(field.Name);
                    if (fName.ToLower().Contains("instance"))
                    {
                        Console.WriteLine($"  FIELD: {fName}");
                    }
                }
            }
        }
    }
}
