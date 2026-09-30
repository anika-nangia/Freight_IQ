# Simple native PowerShell HTTP Server for FreightIQ (zero dependencies required)
#
# Also proxies /api/* to the FastAPI backend (default 127.0.0.1:8000) so the page and
# the API share an origin. Without this the browser blocks the API call from the static
# server, and opening index.html as file:// blocks it for the same reason.
param([int]$Port = 3000, [string]$ApiTarget = "http://127.0.0.1:8000")

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$Port/")
try {
    $listener.Start()
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " FreightIQ Server running at http://localhost:$Port/" -ForegroundColor Cyan
    Write-Host " Press Ctrl+C in this terminal to stop the server." -ForegroundColor Yellow
    Write-Host "==========================================================" -ForegroundColor Green
    Start-Process "http://localhost:$Port/"

    while ($listener.IsListening) {
        $context = $listener.GetContext()
        $request = $context.Request
        $response = $context.Response
        
        $localPath = $request.Url.LocalPath.TrimStart('/')

        # --- Proxy /api/* to the FastAPI backend ---------------------------
        if ($localPath.StartsWith("api/") -or $localPath -eq "api") {
            try {
                $uri = "$ApiTarget/$($request.Url.LocalPath.TrimStart('/'))"
                if ($request.Url.Query) { $uri = "$uri`?$($request.Url.Query)" }
                $proxy = [System.Net.WebRequest]::Create($uri)
                $proxy.Method = $request.HttpMethod

                # Forward the request body and content type. Without this every POST
                # reaches FastAPI with an empty payload and comes back as a 422, so
                # /api/query/route and /api/contract/compare work when the API is hit
                # directly but fail through the proxy.
                if ($request.HasEntityBody) {
                    $len = [int]$request.ContentLength64
                    if ($len -gt 0) {
                        $proxy.ContentLength = $len
                        if ($request.ContentType) { $proxy.ContentType = $request.ContentType }
                        if ($request.Headers["Accept"]) { $proxy.Accept = $request.Headers["Accept"] }
                        $rs = $proxy.GetRequestStream()
                        $buf2 = New-Object byte[] 8192
                        $total = 0
                        while ($total -lt $len) {
                            $n2 = $request.InputStream.Read($buf2, 0, [Math]::Min(8192, $len - $total))
                            if ($n2 -le 0) { break }
                            $rs.Write($buf2, 0, $n2)
                            $total += $n2
                        }
                        $rs.Close()
                    }
                }

                $resp = $proxy.GetResponse()
                $response.StatusCode = [int]$resp.StatusCode
                $response.ContentType = $resp.ContentType
                $stream = $resp.GetResponseStream()
                $buf = New-Object byte[] 8192
                while (($n = $stream.Read($buf, 0, $buf.Length)) -gt 0) {
                    $response.OutputStream.Write($buf, 0, $n)
                }
                $resp.Close()
            } catch [System.Net.WebException] {
                # Pass the upstream status through instead of masking it, so a genuine
                # 422 from request validation stays visible rather than becoming a 503.
                $upstream = $_.Exception.Response
                if ($upstream) {
                    try { $response.StatusCode = [int]$upstream.StatusCode } catch { $response.StatusCode = 502 }
                    try {
                        $ers = $upstream.GetResponseStream()
                        $ebuf = New-Object byte[] 4096
                        $en = $ers.Read($ebuf, 0, $ebuf.Length)
                        if ($en -gt 0) { $response.OutputStream.Write($ebuf, 0, $en) }
                    } catch { }
                    $upstream.Close()
                } else {
                    $response.StatusCode = 502
                }
            } catch {
                # Backend not running. Return a clear, parseable error so the page can
                # show its offline notice instead of a blank panel.
                $response.StatusCode = 503
                $response.ContentType = "application/json"
                $err = [System.Text.Encoding]::UTF8.GetBytes(
                    '{"detail":"FreightIQ API is not running. Start it with: uvicorn backend.main:app --app-dir freight-intelligence-sih"}')
                $response.OutputStream.Write($err, 0, $err.Length)
            }
            $response.Close()
            continue
        }

        if ([string]::IsNullOrEmpty($localPath) -or $localPath -eq "") {
            $localPath = "index.html"
        }

        $filePath = Join-Path $PSScriptRoot $localPath
        if (Test-Path $filePath -PathType Leaf) {
            $bytes = [System.IO.File]::ReadAllBytes($filePath)
            
            # MIME types
            $ext = [System.IO.Path]::GetExtension($filePath).ToLower()
            switch ($ext) {
                ".html" { $response.ContentType = "text/html" }
                ".css"  { $response.ContentType = "text/css" }
                ".js"   { $response.ContentType = "application/javascript" }
                ".png"  { $response.ContentType = "image/png" }
                ".jpg"  { $response.ContentType = "image/jpeg" }
                ".svg"  { $response.ContentType = "image/svg+xml" }
                ".json" { $response.ContentType = "application/json" }
                default { $response.ContentType = "application/octet-stream" }
            }
            
            $response.ContentLength64 = $bytes.Length
            $response.OutputStream.Write($bytes, 0, $bytes.Length)
        } else {
            $response.StatusCode = 404
            $err = [System.Text.Encoding]::UTF8.GetBytes("404 Not Found")
            $response.OutputStream.Write($err, 0, $err.Length)
        }
        $response.Close()
    }
} finally {
    $listener.Stop()
}
