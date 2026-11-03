param(
    [string]$PortName = "COM3",
    [string]$ApiUrl = "http://127.0.0.1:8000/api/ingest"
)

$ErrorActionPreference = "Stop"
$serial = [System.IO.Ports.SerialPort]::new(
    $PortName,
    115200,
    [System.IO.Ports.Parity]::None,
    8,
    [System.IO.Ports.StopBits]::One
)
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.ReadTimeout = 1000

$numberPattern = '([+-]?(?:\d+(?:\.\d*)?|\.\d+))'
$invariant = [System.Globalization.CultureInfo]::InvariantCulture
$reading = $null
$readingNumber = 0

try {
    $serial.Open()
    Write-Host "[Bridge] Reading ESP32 telemetry from $PortName at 115200 baud."
    Write-Host "[Bridge] Forwarding real USB readings to $ApiUrl. Press Ctrl+C to stop."

    while ($true) {
        try {
            $line = $serial.ReadLine().Trim()
        }
        catch [System.TimeoutException] {
            continue
        }

        if ($line -match 'Reading #\s*(\d+)') {
            $readingNumber = [int]$Matches[1]
            $reading = @{
                device_id   = "esp32-usb-$PortName"
                temperature_c = $null
                humidity_pct  = $null
                ldr_raw       = $null
                lux           = $null
                voltage_v     = $null
                current_ma    = $null
                power_mw      = $null
            }
            continue
        }

        if ($null -eq $reading) {
            continue
        }

        if ($line -match "Temperature:\s*$numberPattern") {
            $reading.temperature_c = [double]::Parse($Matches[1], $invariant)
        }
        elseif ($line -match "Humidity:\s*$numberPattern") {
            $reading.humidity_pct = [double]::Parse($Matches[1], $invariant)
        }
        elseif ($line -match "LDR ADC:\s*(\d+)") {
            $reading.ldr_raw = [int]$Matches[1]
        }
        elseif ($line -match "Panel Voltage:\s*$numberPattern") {
            $reading.voltage_v = [double]::Parse($Matches[1], $invariant)
        }
        elseif ($line -match "Current:\s*$numberPattern") {
            $reading.current_ma = [double]::Parse($Matches[1], $invariant)
        }
        elseif ($line -match "Power:\s*$numberPattern") {
            $reading.power_mw = [double]::Parse($Matches[1], $invariant)
        }
        elseif ($line -match '\[Stats\]\s*Success:') {
            if ($null -eq $reading.ldr_raw -and
                $null -eq $reading.temperature_c -and
                $null -eq $reading.humidity_pct) {
                Write-Warning "[Bridge] Skipping serial reading $readingNumber`: no valid environmental measurements."
                $reading = $null
                continue
            }

            $json = $reading | ConvertTo-Json -Compress
            try {
                $response = Invoke-RestMethod `
                    -Uri $ApiUrl `
                    -Method Post `
                    -ContentType "application/json" `
                    -Body $json
                Write-Host "[Bridge] API $($response.status): forwarded hardware reading $readingNumber; backend source is ESP32."
            }
            catch {
                Write-Warning "[Bridge] Could not forward reading $readingNumber`: $($_.Exception.Message)"
            }
            $reading = $null
        }
    }
}
finally {
    if ($serial.IsOpen) {
        $serial.Close()
    }
    $serial.Dispose()
    Write-Host "[Bridge] Serial port closed."
}
