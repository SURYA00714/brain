using System;
using System.Reflection;
using UnityEngine;
using Kirurobo;

public class InspectUWC
{
    public static void Run() {
        var t = typeof(Kirurobo.UniWindowController);
        foreach (var p in t.GetProperties()) {
            Console.WriteLine("Prop: " + p.Name + " - " + p.PropertyType);
        }
        foreach (var f in t.GetFields()) {
            Console.WriteLine("Field: " + f.Name + " - " + f.FieldType);
        }
    }
}
