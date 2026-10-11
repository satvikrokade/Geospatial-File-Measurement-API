from __future__ import annotations
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from app.schemas.measurements import MeasurementResultSchema
PRIMARY = colors.HexColor('#1a365d')
SECONDARY = colors.HexColor('#2b6cb0')
ACCENT = colors.HexColor('#38a169')
LIGHT_BG = colors.HexColor('#ebf8ff')
TABLE_HEADER = colors.HexColor('#2b6cb0')
TABLE_ALT = colors.HexColor('#f0f4f8')

def _get_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {'title': ParagraphStyle('Title', parent=base['Title'], fontSize=24, textColor=PRIMARY, spaceAfter=6, alignment=TA_CENTER), 'subtitle': ParagraphStyle('Subtitle', parent=base['Normal'], fontSize=12, textColor=SECONDARY, spaceAfter=4, alignment=TA_CENTER), 'section': ParagraphStyle('Section', parent=base['Heading2'], fontSize=14, textColor=PRIMARY, spaceBefore=12, spaceAfter=6, borderPad=2), 'body': ParagraphStyle('Body', parent=base['Normal'], fontSize=9, textColor=colors.HexColor('#2d3748'), spaceAfter=4), 'note': ParagraphStyle('Note', parent=base['Normal'], fontSize=8, textColor=colors.HexColor('#718096'), spaceAfter=4, leftIndent=10), 'warning': ParagraphStyle('Warning', parent=base['Normal'], fontSize=8, textColor=colors.HexColor('#c05621'), spaceAfter=2, leftIndent=10)}

def _make_summary_table(result: MeasurementResultSchema) -> Table:
    data: list[list[str]] = [['Property', 'Value'], ['File Name', result.filename], ['Format', result.format.upper()], ['Source CRS', result.source_crs], ['Calculation Method', result.calculation_method], ['Feature Count', str(result.feature_count)], ['Geometry Types', ', '.join((f'{b.geometry_type} ({b.count})' for b in result.geometry_type_breakdown))]]
    if result.total_area_m2 is not None:
        area_ha = result.total_area_m2 / 10000
        area_km2 = result.total_area_m2 / 1000000
        data.extend([['Total Area (m²)', f'{result.total_area_m2:,.2f}'], ['Total Area (ha)', f'{area_ha:,.4f}'], ['Total Area (km²)', f'{area_km2:,.6f}']])
    if result.total_perimeter_m is not None:
        data.append(['Total Perimeter (m)', f'{result.total_perimeter_m:,.2f}'])
    if result.total_length_m is not None:
        data.append(['Total Length (m)', f'{result.total_length_m:,.2f}'])
    if result.centroid_wgs84:
        data.append(['Centroid (WGS84)', f'Lon: {result.centroid_wgs84.longitude:.6f}, Lat: {result.centroid_wgs84.latitude:.6f}'])
    if result.bounding_box:
        bb = result.bounding_box
        data.append(['Bounding Box', f'[{bb.min_lon:.4f}, {bb.min_lat:.4f}, {bb.max_lon:.4f}, {bb.max_lat:.4f}]'])
    if result.area_statistics:
        stats = result.area_statistics
        data.extend([['Mean Area (m²)', f'{stats.mean_m2:,.2f}'], ['Min Area (m²)', f'{stats.min_m2:,.2f}'], ['Max Area (m²)', f'{stats.max_m2:,.2f}'], ['Median Area (m²)', f'{stats.median_m2:,.2f}']])
    col_widths = [7 * cm, 10 * cm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    style = TableStyle([('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, 0), 10), ('ALIGN', (0, 0), (-1, 0), 'CENTER'), ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'), ('FONTSIZE', (0, 1), (-1, -1), 9), ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'), ('TEXTCOLOR', (0, 1), (0, -1), PRIMARY), *[('BACKGROUND', (0, i), (-1, i), TABLE_ALT) for i in range(2, len(data), 2)], ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5), ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8), ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, TABLE_ALT]), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')])
    table.setStyle(style)
    return table

class ReportService:

    def generate(self, result: MeasurementResultSchema) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm, title=f'Geospatial Measurement Report — {result.filename}', author='Geospatial Measurement API', subject='Area, perimeter, and geometry statistics')
        styles = _get_styles()
        story: list[Any] = []
        story.append(Paragraph('🌍 Geospatial Measurement Report', styles['title']))
        story.append(Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", styles['subtitle']))
        story.append(Paragraph(f'File: <b>{result.filename}</b>', styles['subtitle']))
        story.append(HRFlowable(width='100%', thickness=2, color=PRIMARY))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph('📊 Summary Statistics', styles['section']))
        story.append(_make_summary_table(result))
        story.append(Spacer(1, 0.5 * cm))
        if result.warnings:
            story.append(Paragraph('⚠️ Warnings', styles['section']))
            for w in result.warnings:
                story.append(Paragraph(f'• {w}', styles['warning']))
            story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph('📐 Calculation Method', styles['section']))
        method_text = self._get_method_explanation(result.calculation_method)
        story.append(Paragraph(method_text, styles['body']))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph('<i>Design Decision: Why Geodesic Area?</i>', styles['section']))
        story.append(Paragraph('Computing area from raw latitude/longitude coordinates treats degrees as if they were uniform Euclidean units — this introduces errors of 5–10% at mid-latitudes and larger near the poles. Instead, this API uses <b>pyproj.Geod.geometry_area_perimeter()</b> which integrates the boundary along true geodesic arcs on the WGS84 ellipsoid (a=6378137 m, f=1/298.257223563). Results match PostGIS ST_Area(geography) and QGIS in ellipsoidal mode to within floating-point precision.', styles['body']))
        story.append(Spacer(1, 0.5 * cm))
        story.append(HRFlowable(width='100%', thickness=1, color=SECONDARY))
        story.append(Paragraph(f'File ID: {result.file_id} | Geospatial Measurement API', styles['note']))
        doc.build(story)
        return buffer.getvalue()

    @staticmethod
    def _get_method_explanation(method: str) -> str:
        if method == 'geodesic_wgs84':
            return 'Method: <b>Geodesic WGS84</b><br/>Area and perimeter are computed using geodesic formulas on the WGS84 ellipsoid via pyproj.Geod. This is the most accurate approach for geographic (lat/lon) data and is equivalent to PostGIS ST_Area(geography) with ellipsoidal=true.'
        elif 'projected' in method:
            epsg = method.replace('projected_', '').replace('_', ':').upper()
            return f'Method: <b>Planimetric ({epsg})</b><br/>Source data is in a projected CRS ({epsg}). Area and perimeter are computed directly in projected coordinates (units: metres). Centroid is computed in projected space then back-projected to WGS84.'
        return f'Method: {method}'
