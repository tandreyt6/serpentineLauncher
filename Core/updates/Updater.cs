using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal sealed class UpdateWindow : Form
{
    internal static volatile bool Ending;
    internal static EventWaitHandle Abort;
    internal static EventWaitHandle Block;
    internal static string Reason;
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern bool ShutdownBlockReasonCreate(IntPtr window, string reason);
    [DllImport("user32.dll")] private static extern bool ShutdownBlockReasonDestroy(IntPtr window);
    protected override void SetVisibleCore(bool value) { base.SetVisibleCore(false); }
    protected override void WndProc(ref Message message)
    {
        if (message.Msg == 0x11)
        {
            if (Block != null && Block.WaitOne(0) && (message.LParam.ToInt64() & 0x40000001) == 0)
            {
                ShutdownBlockReasonCreate(Handle, Reason);
                message.Result = IntPtr.Zero;
                return;
            }
            Ending = true;
            if (Abort != null) Abort.Set();
            message.Result = new IntPtr(1);
            return;
        }
        if (message.Msg == 0x16)
        {
            ShutdownBlockReasonDestroy(Handle);
            if (message.WParam != IntPtr.Zero) Environment.Exit(0);
            message.Result = IntPtr.Zero;
            return;
        }
        base.WndProc(ref message);
    }
}

internal static class Updater
{
    private const string Launcher = "SerpantineLauncher.exe";
    private const string Manifest = "launcher-update.json";
    private static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = 16777216 };
    private static readonly HashSet<string> Protected = new HashSet<string>(new[] {
        "builds", "cores", "libs", "logs", "cache", "themes", "theme_sources", ".git", ".venv", ".idea",
        "betathemes", "themeworkbench", "serpantinelauncher.json", "serpantinethemehealth.json", "catalog.json"
    }, StringComparer.OrdinalIgnoreCase);
    private static string Plan, Stage, Target;
    private static EventWaitHandle Abort;
    private static readonly List<string> Changed = new List<string>();
    private static readonly HashSet<string> Existed = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    private static bool Installing;
    private static int Result;
    private static Dictionary<string, object> Resume;
    private static bool ParentExited;
    private static readonly List<IntPtr> ClientHandles = new List<IntPtr>();
    private static readonly List<IntPtr> JobHandles = new List<IntPtr>();

    [DllImport("user32.dll")] private static extern bool GetSystemMetrics(int index);
    [DllImport("kernel32.dll")] private static extern uint GetProcessId(IntPtr process);
    [DllImport("kernel32.dll")] private static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);
    [DllImport("kernel32.dll")] private static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll")] private static extern IntPtr GetCurrentThread();
    [DllImport("kernel32.dll")] private static extern bool SetThreadPriority(IntPtr thread, int priority);

    [STAThread]
    private static int Main(string[] args)
    {
        if (args.Length != 2 || args[0] != "--plan") return 2;
        try
        {
            Plan = Path.GetFullPath(args[1]);
            Stage = Path.GetDirectoryName(Plan);
            Dictionary<string, object> config = Read(Plan);
            if (Number(config, "schema") != 2 || Text(config, "executable") != Launcher) throw new InvalidDataException("Invalid updater plan");
            Abort = EventWaitHandle.OpenExisting(Text(config, "abortEvent"));
            UpdateWindow.Abort = Abort;
            if (config.ContainsKey("blockEvent"))
            {
                UpdateWindow.Block = EventWaitHandle.OpenExisting(Text(config, "blockEvent"));
                UpdateWindow.Reason = Text(config, "shutdownReason");
            }
            using (EventWaitHandle ready = EventWaitHandle.OpenExisting(Text(config, "readyEvent")))
            using (UpdateWindow window = new UpdateWindow())
            {
                window.Text = "Serpentine Launcher Updater";
                IntPtr handle = window.Handle;
                Thread worker = new Thread(delegate() {
                    bool background = SetThreadPriority(GetCurrentThread(), 0x10000);
                    try { Install(config, ready); }
                    catch (Exception error)
                    {
                        Failed(error);
                        Result = 1;
                        if (ParentExited && Resume != null && !UpdateWindow.Ending && !GetSystemMetrics(0x2000))
                            try { StartResumed(); } catch { }
                    }
                    finally
                    {
                        KeepClients();
                        foreach (IntPtr item in ClientHandles.Concat(JobHandles)) CloseHandle(item);
                        if (background) SetThreadPriority(GetCurrentThread(), 0x20000);
                        if (!window.IsDisposed) window.BeginInvoke(new Action(Application.Exit));
                    }
                });
                worker.IsBackground = true;
                window.BeginInvoke(new Action(worker.Start));
                Application.Run(window);
            }
        }
        catch (Exception error) { Failed(error); return 1; }
        finally { if (Abort != null) Abort.Dispose(); if (UpdateWindow.Block != null) UpdateWindow.Block.Dispose(); }
        return Result;
    }

    private static void Check()
    {
        if (UpdateWindow.Ending || (GetSystemMetrics(0x2000) && (UpdateWindow.Block == null || !UpdateWindow.Block.WaitOne(0))) || (Abort != null && Abort.WaitOne(0)) || File.Exists(Plan + ".cancel"))
            throw new OperationCanceledException("Update cancelled");
    }

    private static Dictionary<string, object> Read(string path)
    {
        if (new FileInfo(path).Length > 16777216) throw new InvalidDataException("Metadata is too large");
        return Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(path, Encoding.UTF8));
    }

    private static string Text(Dictionary<string, object> data, string key) { return (string)data[key]; }
    private static long Number(Dictionary<string, object> data, string key) { return Convert.ToInt64(data[key]); }
    private static string Hash(string path)
    {
        using (FileStream stream = File.OpenRead(path))
        using (SHA256 algorithm = SHA256.Create())
            return BitConverter.ToString(algorithm.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }

    private static string Safe(string root, string relative)
    {
        if (String.IsNullOrEmpty(relative) || relative.IndexOfAny(new[] { '\\', ':', '\0' }) >= 0 || Path.IsPathRooted(relative))
            throw new InvalidDataException("Unsafe update path");
        string[] parts = relative.Split('/');
        if (Protected.Contains(parts[0])) throw new InvalidDataException("Protected user data in update");
        foreach (string part in parts)
            if (part == "" || part == "." || part == ".." || part.EndsWith(".") || part.EndsWith(" ") || Regex.IsMatch(part, @"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$", RegexOptions.IgnoreCase))
                throw new InvalidDataException("Unsafe update path");
        root = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar);
        string full = Path.GetFullPath(Path.Combine(root, relative));
        if (!full.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Update path escapes root");
        for (string cursor = full; cursor != null; cursor = Path.GetDirectoryName(cursor))
        {
            if ((File.Exists(cursor) || Directory.Exists(cursor)) && (File.GetAttributes(cursor) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Update path contains reparse point");
            if (String.Equals(cursor, root, StringComparison.OrdinalIgnoreCase)) break;
        }
        return full;
    }

    private static Dictionary<string, object> Validate(Dictionary<string, object> manifest, string version)
    {
        if (Number(manifest, "schema") != 1 || Text(manifest, "platform") != "windows-x64" || Text(manifest, "executable") != Launcher ||
            Text(manifest, "version").TrimStart('v', 'V') != version.TrimStart('v', 'V')) throw new InvalidDataException("Invalid update manifest");
        Dictionary<string, object> files = (Dictionary<string, object>)manifest["files"];
        if (files.Count < 1 || files.Count > 40000 || !files.ContainsKey(Launcher)) throw new InvalidDataException("Invalid update file list");
        HashSet<string> seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        long total = 0;
        foreach (KeyValuePair<string, object> entry in files)
        {
            Safe(Target, entry.Key);
            Dictionary<string, object> info = (Dictionary<string, object>)entry.Value;
            long size = Number(info, "size");
            if (!seen.Add(entry.Key) || String.Equals(entry.Key, Manifest, StringComparison.OrdinalIgnoreCase) || size < 0 || !Regex.IsMatch(Text(info, "sha256"), "^[0-9a-f]{64}$"))
                throw new InvalidDataException("Invalid update file");
            total = checked(total + size);
        }
        if (total > 3221225472L) throw new InvalidDataException("Update is too large");
        return files;
    }

    private static Dictionary<string, object> Extract(Dictionary<string, object> config, string payload)
    {
        string archive = Path.GetFullPath(Text(config, "archive"));
        if (new FileInfo(archive).Length != Number(config, "size") || new FileInfo(archive).Length > 1073741824 || Hash(archive) != Text(config, "sha256"))
            throw new InvalidDataException("Update archive checksum mismatch");
        using (ZipArchive zip = ZipFile.OpenRead(archive))
        {
            if (zip.Entries.Count > 40001) throw new InvalidDataException("Too many archive entries");
            ZipArchiveEntry manifestEntry = zip.GetEntry(Manifest);
            if (manifestEntry == null || manifestEntry.Length > 16777216) throw new InvalidDataException("Missing update manifest");
            Dictionary<string, object> manifest;
            using (StreamReader input = new StreamReader(manifestEntry.Open(), Encoding.UTF8))
                manifest = Json.Deserialize<Dictionary<string, object>>(input.ReadToEnd());
            Dictionary<string, object> files = Validate(manifest, Text(config, "version"));
            HashSet<string> seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            if (zip.Entries.Count != files.Count + 1) throw new InvalidDataException("Unexpected archive content");
            foreach (ZipArchiveEntry entry in zip.Entries)
            {
                Check();
                string path = Safe(payload, entry.FullName);
                if (!seen.Add(entry.FullName) || (entry.ExternalAttributes >> 16 & 0xF000) == 0xA000) throw new InvalidDataException("Invalid archive entry");
                Dictionary<string, object> info = null;
                if (entry.FullName != Manifest)
                {
                    object declared;
                    if (!files.TryGetValue(entry.FullName, out declared)) throw new InvalidDataException("Unexpected archive entry");
                    info = (Dictionary<string, object>)declared;
                    if (entry.Length != Number(info, "size")) throw new InvalidDataException("Invalid archive entry size");
                }
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                using (Stream input = entry.Open())
                using (FileStream output = new FileStream(path, FileMode.CreateNew))
                {
                    byte[] buffer = new byte[262144];
                    int read;
                    long count = 0;
                    while ((read = input.Read(buffer, 0, buffer.Length)) != 0)
                    {
                        Check();
                        count += read;
                        if (count > entry.Length) throw new InvalidDataException("Invalid archive content size");
                        output.Write(buffer, 0, read);
                    }
                    if (count != entry.Length) throw new InvalidDataException("Truncated archive entry");
                }
                if (info != null && Hash(path) != Text(info, "sha256")) throw new InvalidDataException("Update file checksum mismatch");
            }
            return files;
        }
    }

    private static void Replace(string source, string target)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(target));
        string temporary = target + ".update-" + Guid.NewGuid().ToString("N");
        try
        {
            File.Copy(source, temporary, false);
            Check();
            if (File.Exists(target)) File.Replace(temporary, target, null);
            else File.Move(temporary, target);
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }

    private static void Install(Dictionary<string, object> config, EventWaitHandle ready)
    {
        Target = Path.GetFullPath(Text(config, "target")).TrimEnd(Path.DirectorySeparatorChar);
        if (!Directory.Exists(Target) || Target == Path.GetPathRoot(Target).TrimEnd(Path.DirectorySeparatorChar)) throw new InvalidDataException("Invalid installation directory");
        string launcher = Safe(Target, Launcher);
        Process parent = Process.GetProcessById((int)Number(config, "pid"));
        using (parent)
        {
            if (!String.Equals(Path.GetFullPath(parent.MainModule.FileName), launcher, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Unexpected launcher process");
            IntPtr parentHandle = parent.Handle;
            Check();
            ready.Set();
            while (!parent.WaitForExit(100)) { AcceptClients(); Check(); }
        }
        ParentExited = true;
        AcceptClients();
        Check();
        string commitPath = Plan + ".commit";
        if (!File.Exists(commitPath)) throw new OperationCanceledException("Launcher did not authorize installation");
        Dictionary<string, object> commit = Read(commitPath);
        string payload = Path.Combine(Stage, "install-" + Guid.NewGuid().ToString("N"));
        Dictionary<string, object> files = Extract(config, payload);
        Check();
        using (FileStream installLock = new FileStream(Safe(Target, "launcher-update.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None))
        {
            string installedManifest = Safe(Target, Manifest);
            Dictionary<string, object> oldFiles = new Dictionary<string, object>();
            if (File.Exists(installedManifest))
            {
                Dictionary<string, object> old = Read(installedManifest);
                oldFiles = Validate(old, Text(old, "version"));
            }
            string[] all = files.Keys.Concat(oldFiles.Keys).Concat(new[] { Manifest }).Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
            foreach (string name in all)
            {
                Check();
                string path = Safe(Target, name);
                if (Directory.Exists(path)) throw new IOException("Update collides with a directory");
                if (File.Exists(path))
                {
                    string saved = Safe(Path.Combine(Stage, "backup"), name);
                    Directory.CreateDirectory(Path.GetDirectoryName(saved));
                    File.Copy(path, saved, false);
                    Existed.Add(name);
                }
            }
            Installing = true;
            foreach (string name in files.Keys.Where(n => n != Launcher).OrderBy(n => n).Concat(new[] { Launcher, Manifest }))
            {
                Check();
                Changed.Add(name);
                Replace(Safe(payload, name), Safe(Target, name));
            }
            foreach (string name in oldFiles.Keys.Where(n => !files.ContainsKey(n)))
            {
                Check();
                Changed.Add(name);
                string path = Safe(Target, name);
                if (File.Exists(path)) File.Delete(path);
            }
            Check();
            File.WriteAllText(Path.Combine(Stage, "result.json"), Json.Serialize(new { status = "installed", version = config["version"], target = Target }));
            Installing = false;
        }
        Check();
        if (commit.ContainsKey("restart") && Object.Equals(commit["restart"], true))
        {
            if (Resume != null) StartResumed();
            else Process.Start(new ProcessStartInfo(launcher) { WorkingDirectory = Target, UseShellExecute = false });
        }
    }

    private static void AcceptClients()
    {
        string path = Plan + ".handoff";
        if (Resume != null || !File.Exists(path)) return;
        Dictionary<string, object> data = Read(path);
        foreach (Dictionary<string, object> item in ((IEnumerable)data["clients"]).Cast<Dictionary<string, object>>())
        {
            Dictionary<string, object> handles = (Dictionary<string, object>)item["handles"];
            IntPtr process = new IntPtr(Number(handles, "process"));
            IntPtr job = new IntPtr(Number(handles, "job"));
            if (GetProcessId(process) != Number(handles, "pid")) throw new InvalidDataException("Invalid transferred process handle");
            ClientHandles.Add(process);
            JobHandles.Add(job);
        }
        data["updaterPid"] = Process.GetCurrentProcess().Id;
        data["target"] = Target;
        Resume = data;
        File.WriteAllText(Plan + ".resume", Json.Serialize(data));
        File.WriteAllText(Plan + ".accepted", "ready");
    }

    private static void StartResumed()
    {
        string launcher = Safe(Target, Launcher);
        Process.Start(new ProcessStartInfo(launcher) {
            WorkingDirectory = Target, UseShellExecute = false,
            Arguments = "--resume-update \"" + Plan + "\"",
            WindowStyle = ProcessWindowStyle.Hidden
        });
    }

    private static void KeepClients()
    {
        if (Resume == null) return;
        DateTime deadline = DateTime.UtcNow.AddSeconds(60);
        while (true)
        {
            string path = Plan + ".restored";
            if (File.Exists(path))
                try
                {
                    Dictionary<string, object> restored = Read(path);
                    using (Process owner = Process.GetProcessById((int)Number(restored, "pid")))
                        if (Text(restored, "token") == Text(Resume, "token") && String.Equals(owner.MainModule.FileName, Safe(Target, Launcher), StringComparison.OrdinalIgnoreCase))
                        {
                            return;
                        }
                }
                catch { }
            if (DateTime.UtcNow > deadline && (ClientHandles.Count == 0 || ClientHandles.All(handle => WaitForSingleObject(handle, 0) == 0))) return;
            Thread.Sleep(100);
        }
    }

    private static void Failed(Exception error)
    {
        if (Stage == null) return;
        List<string> rollbackErrors = new List<string>();
        if (Installing && !UpdateWindow.Ending)
            foreach (string name in Changed.AsEnumerable().Reverse().Distinct())
                try
                {
                    string path = Safe(Target, name);
                    if (Existed.Contains(name))
                    {
                        string saved = Safe(Path.Combine(Stage, "backup"), name);
                        if (!File.Exists(path) || Hash(path) != Hash(saved)) File.Copy(saved, path, true);
                    }
                    else if (File.Exists(path)) File.Delete(path);
                }
                catch (Exception failure) { rollbackErrors.Add(failure.Message); }
        try { File.WriteAllText(Path.Combine(Stage, "result.json"), Json.Serialize(new { status = "failed", error = error.Message, rollbackErrors = rollbackErrors, target = Target })); }
        catch { }
    }
}
