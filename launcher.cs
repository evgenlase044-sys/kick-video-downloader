using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace KickStudio
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                string electronExe = Path.Combine(baseDir, "node_modules", "electron", "dist", "electron.exe");

                ProcessStartInfo psi;

                if (File.Exists(electronExe))
                {
                    psi = new ProcessStartInfo
                    {
                        FileName = electronExe,
                        Arguments = "\".\"",
                        WorkingDirectory = baseDir,
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };
                }
                else
                {
                    psi = new ProcessStartInfo
                    {
                        FileName = "cmd.exe",
                        Arguments = "/c npm start",
                        WorkingDirectory = baseDir,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        WindowStyle = ProcessWindowStyle.Hidden
                    };
                }

                Process.Start(psi);
            }
            catch (Exception ex)
            {
                MessageBox.Show("Ошибка запуска Kick Studio: " + ex.Message, "Kick Studio Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }
}
