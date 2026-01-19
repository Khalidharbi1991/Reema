# PowerShell Script to Convert HTML to DOCX and PDF using Microsoft Word
# This script uses Word COM automation to create professional documents

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  CONVERTING Workstation Security Patches SOP" -ForegroundColor Cyan
Write-Host "  HTML -> DOCX -> PDF" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# Define paths
$htmlFile = "$PSScriptRoot\output\html\Workstation_Security_Patches_SOP.html"
$docxFile = "$PSScriptRoot\output\docx\Workstation_Security_Patches_SOP.docx"
$pdfFile = "$PSScriptRoot\output\pdf\Workstation_Security_Patches_SOP.pdf"

# Create output directories if they don't exist
Write-Host "[1/5] Creating output directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$PSScriptRoot\output\docx" | Out-Null
New-Item -ItemType Directory -Force -Path "$PSScriptRoot\output\pdf" | Out-Null
Write-Host "      Output directories ready" -ForegroundColor Green

# Check if HTML file exists
if (-not (Test-Path $htmlFile)) {
    Write-Host "ERROR: HTML file not found at: $htmlFile" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/5] Opening Microsoft Word..." -ForegroundColor Yellow

# Create Word application object
try {
    $Word = New-Object -ComObject Word.Application
    $Word.Visible = $false
    Write-Host "      Microsoft Word opened successfully" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Could not open Microsoft Word. Is it installed?" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

try {
    Write-Host ""
    Write-Host "[3/5] Converting HTML to DOCX..." -ForegroundColor Yellow

    # Open HTML file
    $Doc = $Word.Documents.Open($htmlFile)

    # Save as DOCX (format code 16 = wdFormatXMLDocument)
    $Doc.SaveAs([ref]$docxFile, [ref]16)
    Write-Host "      DOCX created: $docxFile" -ForegroundColor Green

    Write-Host ""
    Write-Host "[4/5] Converting DOCX to PDF..." -ForegroundColor Yellow

    # Save as PDF (format code 17 = wdFormatPDF)
    $Doc.SaveAs([ref]$pdfFile, [ref]17)
    Write-Host "      PDF created: $pdfFile" -ForegroundColor Green

    # Close document
    $Doc.Close()

    Write-Host ""
    Write-Host "[5/5] Cleaning up..." -ForegroundColor Yellow

} catch {
    Write-Host "ERROR during conversion: $_.Exception.Message" -ForegroundColor Red
    if ($Doc) { $Doc.Close([ref]$false) }
} finally {
    # Quit Word
    $Word.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($Word) | Out-Null
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
    Write-Host "      Microsoft Word closed" -ForegroundColor Green
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  CONVERSION COMPLETE!" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Generated Files:" -ForegroundColor White
Write-Host "  DOCX: $docxFile" -ForegroundColor Cyan
Write-Host "  PDF:  $pdfFile" -ForegroundColor Cyan
Write-Host ""

# Check if files were created
if ((Test-Path $docxFile) -and (Test-Path $pdfFile)) {
    $docxSize = (Get-Item $docxFile).Length / 1KB
    $pdfSize = (Get-Item $pdfFile).Length / 1KB

    Write-Host "File Sizes:" -ForegroundColor White
    Write-Host "  DOCX: $([math]::Round($docxSize, 2)) KB" -ForegroundColor Green
    Write-Host "  PDF:  $([math]::Round($pdfSize, 2)) KB" -ForegroundColor Green
    Write-Host ""
    Write-Host "SUCCESS! Both files created successfully!" -ForegroundColor Green

    # Ask if user wants to open the files
    Write-Host ""
    $openFiles = Read-Host "Would you like to open the DOCX file? (Y/N)"
    if ($openFiles -eq "Y" -or $openFiles -eq "y") {
        Start-Process $docxFile
    }

} else {
    Write-Host "WARNING: One or more files may not have been created successfully." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
