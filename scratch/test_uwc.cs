using System;
using UnityEngine;
using Kirurobo;

public class TestUWC
{
    public static void Check() {
        var uwc = Kirurobo.UniWindowController.current;
        var uwc2 = UnityEngine.Object.FindObjectOfType<Kirurobo.UniWindowController>();
    }
}
