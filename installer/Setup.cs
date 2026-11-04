using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Win32;

internal static class SetupProgram
{
    const string Product = "XD SVN Tools";
    const string Version = "__APP_VERSION__";
    const string Marker = "XD-SVN-Tools-owned-files-v1";
    const string BackupKey = @"Software\XD SVN Tools\IntegrationBackup";
    const string UninstallKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\XD-SVN-Tools";
    static readonly string Root = Path.GetFullPath(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "XD-SVN-Tools"));
    static readonly string Group = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "XD SVN Tools");
    static readonly string OwnerFile = Path.Combine(Root, ".installed-files.txt");
    static readonly string[] ToolKeys = { @"Software\TortoiseSVN\DiffTools", @"Software\TortoiseSVN\MergeTools" };
    static readonly string[] Names = { "Diff", "Merge" };
    static readonly string[] Commands = {
        "\"" + Path.Combine(Root,"XD-SVN-Tools.exe") + "\" diff --base \"%base\" --mine \"%mine\"",
        "\"" + Path.Combine(Root,"XD-SVN-Tools.exe") + "\" merge --base \"%base\" --mine \"%mine\" --theirs \"%theirs\" --merged \"%merged\""
    };
    static bool silent;
    static string logPath;

    [STAThread]
    static int Main(string[] args)
    {
        silent = Array.IndexOf(args,"--silent") >= 0;
        foreach (string arg in args) if (arg.StartsWith("--log=")) logPath = arg.Substring(6);
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        try {
#if UNINSTALLER
            return Uninstall(args);
#else
            if (silent) { Install(); return 0; }
            Application.Run(new InstallForm());
            return ResultCode;
#endif
        } catch(Exception ex) {
            Log(ex.ToString());
            if (!silent) MessageBox.Show(ex.Message,Product,MessageBoxButtons.OK,MessageBoxIcon.Error);
            return 2;
        }
    }
    internal static int ResultCode = 1;
    static void Log(string text) { if (!String.IsNullOrEmpty(logPath)) File.AppendAllText(logPath,DateTime.Now.ToString("s")+" "+text+Environment.NewLine); }
    static bool Owned() { return File.Exists(OwnerFile) && File.ReadAllLines(OwnerFile).Length > 0 && File.ReadAllLines(OwnerFile)[0] == Marker; }
    static bool Installed() { return Owned() && File.Exists(Path.Combine(Root,"XD-SVN-Tools.exe")) && File.Exists(Path.Combine(Root,"XD-SVN-Tools-Uninstall.exe")); }

    static string SafePath(string relative)
    {
        if (String.IsNullOrEmpty(relative) || Path.IsPathRooted(relative) || relative.IndexOf(':') >= 0)
            throw new InvalidDataException("安装包路径无效。");
        string full = Path.GetFullPath(Path.Combine(Root,relative.Replace('/',Path.DirectorySeparatorChar)));
        if (!full.StartsWith(Root+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("安装包路径越界。");
        return full;
    }

    static void BackupIntegration()
    {
        using (RegistryKey key = Registry.CurrentUser.CreateSubKey(BackupKey)) {
            if (Object.Equals(key.GetValue("Complete"),1)) return;
            for(int i=0;i<2;i++) {
                using (RegistryKey old = Registry.CurrentUser.OpenSubKey(ToolKeys[i])) {
                    object value = old == null ? null : old.GetValue(".xd",null,RegistryValueOptions.DoNotExpandEnvironmentNames);
                    key.SetValue(Names[i]+"Had",value == null ? 0 : 1,RegistryValueKind.DWord);
                    if (value != null) {
                        RegistryValueKind kind = old.GetValueKind(".xd");
                        if (!(value is string)) throw new InvalidOperationException("已有 .xd 设置不是字符串，已停止安装以保留原配置。");
                        key.SetValue(Names[i]+"Value",(string)value,RegistryValueKind.String);
                        key.SetValue(Names[i]+"Kind",(int)kind,RegistryValueKind.DWord);
                    }
                }
            }
            key.SetValue("Complete",1,RegistryValueKind.DWord);
        }
    }
    static void RegisterIntegration()
    {
        BackupIntegration();
        for(int i=0;i<2;i++) using(RegistryKey k=Registry.CurrentUser.CreateSubKey(ToolKeys[i])) k.SetValue(".xd",Commands[i],RegistryValueKind.String);
        using(RegistryKey k=Registry.CurrentUser.CreateSubKey(UninstallKey)) {
            string uninstaller = "\""+Path.Combine(Root,"XD-SVN-Tools-Uninstall.exe")+"\"";
            k.SetValue("DisplayName",Product+"（TortoiseSVN XD 对比与合并）");
            k.SetValue("DisplayVersion",Version);
            k.SetValue("Publisher",Product);
            k.SetValue("InstallLocation",Root);
            k.SetValue("DisplayIcon",Path.Combine(Root,"XD-SVN-Tools.exe"));
            k.SetValue("UninstallString",uninstaller);
            k.SetValue("QuietUninstallString",uninstaller+" --silent");
            k.SetValue("NoModify",1,RegistryValueKind.DWord);
            k.SetValue("NoRepair",1,RegistryValueKind.DWord);
        }
        Directory.CreateDirectory(Group);
        Shortcut(Path.Combine(Group,"XD SVN Tools.lnk"),Path.Combine(Root,"XD-SVN-Tools.exe"));
        Shortcut(Path.Combine(Group,"卸载 XD SVN Tools.lnk"),Path.Combine(Root,"XD-SVN-Tools-Uninstall.exe"));
    }
    static void Shortcut(string path,string target)
    {
        Type shellType = Type.GetTypeFromProgID("WScript.Shell");
        dynamic shell = Activator.CreateInstance(shellType);
        dynamic shortcut = shell.CreateShortcut(path);
        shortcut.TargetPath = target;
        shortcut.WorkingDirectory = Root;
        shortcut.Description = Product;
        shortcut.Save();
        System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shortcut);
        System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell);
    }
    static void RestoreIntegration()
    {
        using(RegistryKey backup = Registry.CurrentUser.OpenSubKey(BackupKey)) {
            if (backup == null || !Object.Equals(backup.GetValue("Complete"),1)) throw new InvalidOperationException("找不到安装前的设置备份，已停止卸载。");
            for(int i=0;i<2;i++) using(RegistryKey key=Registry.CurrentUser.CreateSubKey(ToolKeys[i])) {
                string current = key.GetValue(".xd",null,RegistryValueOptions.DoNotExpandEnvironmentNames) as string;
                if (!String.Equals(current,Commands[i],StringComparison.OrdinalIgnoreCase)) {
                    Log("保留安装后由用户更改的设置："+ToolKeys[i]);
                    continue;
                }
                if (Object.Equals(backup.GetValue(Names[i]+"Had"),1))
                    key.SetValue(".xd",(string)backup.GetValue(Names[i]+"Value","",RegistryValueOptions.DoNotExpandEnvironmentNames),(RegistryValueKind)(int)backup.GetValue(Names[i]+"Kind",(int)RegistryValueKind.String));
                else key.DeleteValue(".xd",false);
            }
        }
        Registry.CurrentUser.DeleteSubKeyTree(BackupKey,false);
        Registry.CurrentUser.DeleteSubKeyTree(UninstallKey,false);
        foreach(string name in new[]{"XD SVN Tools.lnk","卸载 XD SVN Tools.lnk"}) {
            string path = Path.Combine(Group,name);
            if(File.Exists(path)) File.Delete(path);
        }
        if(Directory.Exists(Group) && Directory.GetFileSystemEntries(Group).Length==0) Directory.Delete(Group);
    }

    internal static void Install()
    {
        bool upgrading=Installed();
        if(!upgrading && Directory.Exists(Root) && Directory.GetFileSystemEntries(Root).Length != 0)
            throw new InvalidOperationException("安装目录已有其他文件或安装不完整。请先检查：\n"+Root);
        string[] previousManifest=upgrading?File.ReadAllLines(OwnerFile):new string[0];
        HashSet<string> previousOwned=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        for(int i=1;i<previousManifest.Length;i++) previousOwned.Add(previousManifest[i]);
        // Check locks before changing any installed files; never terminate user processes.
        foreach(string relative in previousOwned) {
            string path=SafePath(relative);
            if(File.Exists(path)) {
                try { using(FileStream f=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.None)) {} }
                catch(IOException) { throw new InvalidOperationException("请先关闭 XD SVN Tools 的所有对比和合并窗口，再运行升级。"); }
            }
        }
        string backupDirectory=Path.Combine(Path.GetTempPath(),"XD-SVN-Upgrade-"+Guid.NewGuid().ToString("N"));
        List<string> owned = new List<string>();
        List<string> backedUp = new List<string>();
        bool registered = false;
        try {
            using(Stream stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip")) {
                if(stream==null) throw new InvalidDataException("安装包缺少程序资源。");
                using(ZipArchive archive=new ZipArchive(stream,ZipArchiveMode.Read)) {
                    foreach(ZipArchiveEntry entry in archive.Entries) {
                        const string prefix="XD-SVN-Tools/";
                        string name=entry.FullName.Replace('\\','/');
                        if(!name.StartsWith(prefix,StringComparison.Ordinal)) throw new InvalidDataException("未知的安装包目录。");
                        string relative=name.Substring(prefix.Length);
                        if(relative.Length==0 || relative.EndsWith("/")) continue;
                        string path=SafePath(relative);
                        if(owned.Contains(relative)) throw new InvalidDataException("安装包包含重名文件。");
                        if(File.Exists(path)) {
                            if(!previousOwned.Contains(relative)) throw new InvalidOperationException("安装目标存在非本工具文件，已停止覆盖："+path);
                            string backupPath=Path.Combine(backupDirectory,relative);
                            Directory.CreateDirectory(Path.GetDirectoryName(backupPath));
                            File.Copy(path,backupPath);
                            backedUp.Add(relative);
                        }
                        Directory.CreateDirectory(Path.GetDirectoryName(path));
                        owned.Add(relative);
                        using(Stream input=entry.Open()) using(FileStream output=new FileStream(path,FileMode.Create,FileAccess.Write)) input.CopyTo(output);
                    }
                }
            }
            if(!owned.Contains("XD-SVN-Tools.exe") || !owned.Contains("XD-SVN-Tools-Uninstall.exe")) throw new InvalidDataException("安装包不完整。");
            HashSet<string> allOwned=new HashSet<string>(previousOwned,StringComparer.OrdinalIgnoreCase);
            foreach(string relative in owned) allOwned.Add(relative);
            File.WriteAllLines(OwnerFile,new List<string>(new[]{Marker}).ConcatWith(allOwned));
            registered = true;
            RegisterIntegration();
            Log("Installed and registered: "+Root);
        } catch {
            if(registered && !upgrading) { try { RestoreIntegration(); } catch(Exception ex) { Log("Rollback integration: "+ex.Message); } }
            foreach(string relative in owned) {
                if(backedUp.Contains(relative)) File.Copy(Path.Combine(backupDirectory,relative),SafePath(relative),true);
                else if(File.Exists(SafePath(relative))) File.Delete(SafePath(relative));
            }
            if(upgrading) File.WriteAllLines(OwnerFile,previousManifest);
            else if(File.Exists(OwnerFile)) File.Delete(OwnerFile);
            RemoveEmptyDirectories();
            throw;
        } finally {
            foreach(string relative in backedUp) { try { File.Delete(Path.Combine(backupDirectory,relative)); } catch {} }
            if(Directory.Exists(backupDirectory)) {
                string[] dirs=Directory.GetDirectories(backupDirectory,"*",SearchOption.AllDirectories);
                Array.Sort(dirs,(a,b)=>b.Length.CompareTo(a.Length));
                foreach(string dir in dirs) if(Directory.GetFileSystemEntries(dir).Length==0) Directory.Delete(dir);
                if(Directory.GetFileSystemEntries(backupDirectory).Length==0) Directory.Delete(backupDirectory);
            }
        }
    }
    static IEnumerable<string> ConcatWith(this List<string> first,IEnumerable<string> rest) { foreach(string s in first) yield return s; foreach(string s in rest) yield return s; }
    static void RemoveEmptyDirectories()
    {
        if(!Directory.Exists(Root)) return;
        string[] dirs=Directory.GetDirectories(Root,"*",SearchOption.AllDirectories);
        Array.Sort(dirs,(a,b)=>b.Length.CompareTo(a.Length));
        foreach(string dir in dirs) if(Directory.GetFileSystemEntries(dir).Length==0) Directory.Delete(dir);
        if(Directory.GetFileSystemEntries(Root).Length==0) Directory.Delete(Root);
    }
    static int Uninstall(string[] args)
    {
        bool cleanup=Array.IndexOf(args,"--cleanup")>=0;
        if(!Owned()) throw new InvalidOperationException("未找到本工具的安装记录。不会删除任何文件。");
        if(!cleanup && !silent && MessageBox.Show("卸载 XD SVN Tools，并恢复安装前的 TortoiseSVN .xd 设置？",Product,MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes) return 1;
        if(!cleanup) {
            string copy=Path.Combine(Path.GetTempPath(),"XD-SVN-Tools-Uninstall-"+Guid.NewGuid().ToString("N")+".exe");
            File.Copy(Assembly.GetExecutingAssembly().Location,copy);
            string options="--cleanup --parent="+Process.GetCurrentProcess().Id+(silent?" --silent":"");
            if(!String.IsNullOrEmpty(logPath)) options+=" --log=\""+logPath+"\"";
            Process.Start(new ProcessStartInfo(copy,options){UseShellExecute=false});
            return 0;
        }
        foreach(string arg in args) if(arg.StartsWith("--parent=")) { try { Process.GetProcessById(Int32.Parse(arg.Substring(9))).WaitForExit(15000); } catch(ArgumentException) {} }
        string[] manifest=File.ReadAllLines(OwnerFile);
        List<string> paths=new List<string>();
        for(int i=1;i<manifest.Length;i++) paths.Add(SafePath(manifest[i]));
        // Fail before changing registry if an owned file is currently locked.
        foreach(string path in paths) if(File.Exists(path)) using(FileStream f=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.None)) {}
        RestoreIntegration();
        foreach(string path in paths) if(File.Exists(path)) File.Delete(path);
        File.Delete(OwnerFile);
        RemoveEmptyDirectories();
        Log("Uninstalled; integration restored.");
        if(!silent) MessageBox.Show("已卸载，TortoiseSVN 原有 .xd 设置已恢复。",Product,MessageBoxButtons.OK,MessageBoxIcon.Information);
        // The temporary helper is outside the installation and can be removed by Windows temp cleanup.
        return 0;
    }
    sealed class InstallForm : Form
    {
        readonly Button install=new Button();
        readonly Label status=new Label();
        bool installing;
        internal InstallForm()
        {
            Text="XD SVN Tools 安装";
            ClientSize=new Size(570,355);
            StartPosition=FormStartPosition.CenterScreen;
            FormBorderStyle=FormBorderStyle.FixedDialog;
            MaximizeBox=false;
            FormClosing+=(sender,e)=>{if(installing)e.Cancel=true;};
            Font=new Font("Microsoft YaHei UI",10);
            Controls.Add(new Label {Text="让 TortoiseSVN 直接对比 XD",Font=new Font(Font.FontFamily,18,FontStyle.Bold),AutoSize=true,Location=new Point(28,26)});
            Controls.Add(new Label {Text="安装后，TortoiseSVN 的 .xd 对比和编辑冲突将自动调用本工具。\n\n• 自动设置当前用户，无需管理员权限\n• 保留原设置，卸载时恢复\n• 包含中文界面和完整运行环境",AutoSize=true,Location=new Point(30,79)});
            Controls.Add(new Label {Text="安装目录：\n"+Root,AutoSize=false,Size=new Size(510,52),Location=new Point(30,204),ForeColor=Color.DimGray});
            install.Text=Installed()?"升级到 "+Version+" 并接入":"安装并接入 TortoiseSVN";
            install.Size=new Size(230,42);
            install.Location=new Point(307,291);
            install.Click+=DoInstall;
            Controls.Add(install);
            status.Text="点击即可安装。复杂设计合并后仍需在 XD 中验收。";
            status.Size=new Size(510,28);
            status.Location=new Point(30,260);
            Controls.Add(status);
        }
        async void DoInstall(object sender,EventArgs e)
        {
            if(ResultCode==0) { Close(); return; }
            install.Enabled=false;
            installing=true;
            status.Text="正在安装并设置 TortoiseSVN…";
            try {
                // COM shortcut creation uses an STA thread.
                await RunSta(Install);
                ResultCode=0;
                status.Text="安装完成，TortoiseSVN 已自动接入。";
                install.Text="完成";
            } catch(Exception ex) { status.Text="安装失败，请查看错误信息。"; MessageBox.Show(this,ex.Message,Product,MessageBoxButtons.OK,MessageBoxIcon.Error); }
            install.Enabled=true;
            installing=false;
        }
        static Task RunSta(Action action)
        {
            TaskCompletionSource<bool> result=new TaskCompletionSource<bool>();
            System.Threading.Thread thread=new System.Threading.Thread(()=>{try{action();result.SetResult(true);}catch(Exception ex){result.SetException(ex);}});
            thread.SetApartmentState(System.Threading.ApartmentState.STA);
            thread.Start();
            return result.Task;
        }
    }
}
