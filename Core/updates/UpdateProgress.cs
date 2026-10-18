using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal sealed partial class UpdateWindow
{
    private readonly Dictionary<string, string> Messages;
    private readonly Label Phase = new Label();
    private readonly Label Detail = new Label();
    private readonly Label Count = new Label();
    private readonly ProgressBar Progress = new ProgressBar();
    private readonly Button Dismiss = new Button();
    private bool Display, Busy = true;
    internal bool KeepOpenOnFailure;
    private string LastPhase;
    private int LastPercent = -1;
    private long LastReport;

    internal UpdateWindow(Dictionary<string, object> config)
    {
        string locale = config.ContainsKey("locale") ? (string)config["locale"] : Thread.CurrentThread.CurrentUICulture.TwoLetterISOLanguageName;
        string resource = "updater." + (locale.StartsWith("ru", StringComparison.OrdinalIgnoreCase) ? "ru" : "en") + ".json";
        using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(resource))
        using (StreamReader reader = new StreamReader(stream))
            Messages = new JavaScriptSerializer().Deserialize<Dictionary<string, string>>(reader.ReadToEnd());
        Text = Messages["updates.heading"];
        AutoScaleMode = AutoScaleMode.Dpi;
        ClientSize = new Size(560, 196);
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        ControlBox = false;
        ShowInTaskbar = false;
        Font = SystemFonts.MessageBoxFont;
        Phase.SetBounds(24, 20, 512, 30);
        Phase.Font = new Font(Font.FontFamily, Font.Size + 2, FontStyle.Bold);
        Progress.SetBounds(24, 58, 512, 22);
        Progress.Maximum = 100;
        Count.SetBounds(24, 90, 512, 22);
        Detail.SetBounds(24, 116, 512, 22);
        Detail.AutoEllipsis = true;
        Dismiss.SetBounds(426, 154, 110, 28);
        Dismiss.Text = Messages["updates.install.close"];
        Dismiss.Visible = false;
        Dismiss.Click += delegate { Close(); };
        Controls.AddRange(new Control[] { Phase, Progress, Count, Detail, Dismiss });
        FormClosing += delegate(object sender, FormClosingEventArgs args) { if (Busy && !Ending) args.Cancel = true; };
    }

    protected override bool ShowWithoutActivation { get { return true; } }

    internal void Present(bool visible)
    {
        if (!visible) return;
        Invoke(new Action(delegate {
            Display = true;
            ShowInTaskbar = true;
            Show();
        }));
    }

    internal void Report(string key, int percent, long done, long total, string detail)
    {
        long now = Environment.TickCount & Int32.MaxValue;
        percent = Math.Max(0, Math.Min(100, percent));
        if (key == LastPhase && percent == LastPercent && now - LastReport >= 0 && now - LastReport < 100) return;
        LastPhase = key;
        LastPercent = percent;
        LastReport = now;
        if (IsDisposed || !IsHandleCreated) return;
        BeginInvoke(new Action(delegate {
            Phase.Text = Messages[key];
            Progress.Style = key == "updates.install.waiting" ? ProgressBarStyle.Marquee : ProgressBarStyle.Continuous;
            Progress.Value = percent;
            Count.Text = (total > 0 ? Messages["updates.install.progress"] : Messages["updates.install.percent"]).Replace("%percent%", percent.ToString())
                .Replace("%done%", done.ToString()).Replace("%total%", total.ToString());
            Detail.Text = detail;
        }));
    }

    internal void Failure(Exception error)
    {
        KeepOpenOnFailure = Display && !Ending;
        if (!KeepOpenOnFailure) return;
        BeginInvoke(new Action(delegate {
            Busy = false;
            Phase.Text = Messages["updates.install.failed"];
            Detail.Text = error.Message;
            Count.Text = "";
            Dismiss.Visible = true;
            ControlBox = true;
            AcceptButton = Dismiss;
        }));
    }

    internal void Finish()
    {
        if (IsDisposed || KeepOpenOnFailure) return;
        BeginInvoke(new Action(delegate {
            Busy = false;
            if (!Display || Ending) { Application.Exit(); return; }
            Phase.Text = Messages["updates.install.complete"];
            Progress.Value = 100;
            Detail.Text = "";
            Count.Text = "";
            System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer { Interval = 600 };
            timer.Tick += delegate { timer.Stop(); timer.Dispose(); Application.Exit(); };
            timer.Start();
        }));
    }
}
