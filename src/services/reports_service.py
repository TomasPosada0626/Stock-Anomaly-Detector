from __future__ import annotations

from typing import Any

import pandas as pd


class ReportsService:
    """Build and export business/technical reports in multiple formats."""

    def to_csv_bytes(self, df: pd.DataFrame) -> bytes:
        """Serialize a dataframe into UTF-8 CSV bytes.

        Args:
            df: Source dataframe.

        Returns:
            Encoded CSV payload.
        """
        csv_text = str(df.to_csv(index=True))
        return csv_text.encode("utf-8")

    def to_png_bytes(self, fig: Any) -> bytes:
        """Serialize a Plotly figure to PNG bytes when supported.

        Args:
            fig: Plotly-like figure object.

        Returns:
            PNG bytes, or empty bytes when export is unavailable.
        """
        if hasattr(fig, "to_image"):
            try:
                return bytes(fig.to_image(format="png"))
            except Exception:
                return b""
        return b""

    def _minimal_pdf_from_lines(self, lines: list[str]) -> bytes:
        """Build a minimal single-page PDF from plain text lines.

        Args:
            lines: Text lines to render in the page content stream.

        Returns:
            Binary PDF document.
        """
        escaped_lines = []
        for line in lines:
            text = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            escaped_lines.append(text)

        content_parts = ["BT", "/F1 11 Tf", "50 790 Td"]
        for index, line in enumerate(escaped_lines):
            if index == 0:
                content_parts.append(f"({line}) Tj")
            else:
                content_parts.append("0 -14 Td")
                content_parts.append(f"({line}) Tj")
        content_parts.append("ET")
        content_stream = "\n".join(content_parts).encode("latin-1", errors="replace")

        objects = []
        objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
        objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
        objects.append(
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R /Resources << /Font << /F1 4 0 R >> >> >> endobj\n"
        )
        objects.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
        objects.append(
            f"5 0 obj << /Length {len(content_stream)} >> stream\n".encode("ascii")
            + content_stream
            + b"\nendstream endobj\n"
        )

        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for obj in objects:
            offsets.append(len(pdf))
            pdf.extend(obj)

        xref_offset = len(pdf)
        pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
        pdf.extend(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))

        pdf.extend(
            (
                "trailer\n"
                f"<< /Size {len(offsets)} /Root 1 0 R >>\n"
                "startxref\n"
                f"{xref_offset}\n"
                "%%EOF"
            ).encode("ascii")
        )
        return bytes(pdf)

    def to_pdf_bytes(self, title: str, sections: dict[str, Any]) -> bytes:
        """Build a PDF report from a title and named sections.

        Args:
            title: Report title.
            sections: Mapping of section names to serializable payloads.

        Returns:
            Binary PDF report.
        """
        lines = [title, "QuantVision | Intelligent Financial Analytics Platform", ""]
        for name, payload in sections.items():
            lines.append(f"[{name}]")
            if isinstance(payload, dict):
                for key, value in payload.items():
                    lines.append(f"- {key}: {value}")
            elif isinstance(payload, pd.DataFrame):
                preview = payload.head(15).to_string(index=True).splitlines()
                lines.extend(preview)
            else:
                lines.append(str(payload))
            lines.append("")
        return self._minimal_pdf_from_lines(lines)

    def build_executive_report(
        self, title: str, kpis: dict[str, float], benchmark: pd.DataFrame
    ) -> bytes:
        """Build a compact executive PDF report.

        Args:
            title: Report title.
            kpis: Executive KPI values.
            benchmark: Benchmark dataframe preview.

        Returns:
            Binary PDF report.
        """
        sections = {
            "Executive KPIs": {
                k: f"{v:.4f}" if isinstance(v, (float, int)) else v for k, v in kpis.items()
            },
            "Model Benchmark": benchmark,
        }
        return self.to_pdf_bytes(title=title, sections=sections)

    def build_technical_report(
        self,
        title: str,
        indicators_snapshot: dict[str, float],
        anomaly_table: pd.DataFrame,
    ) -> bytes:
        """Build a technical PDF report with indicators and anomaly summary.

        Args:
            title: Report title.
            indicators_snapshot: Indicator values to include.
            anomaly_table: Tabular anomaly results.

        Returns:
            Binary PDF report.
        """
        sections = {
            "Technical Indicators": {
                k: f"{v:.4f}" if isinstance(v, (float, int)) else v
                for k, v in indicators_snapshot.items()
            },
            "Anomaly Summary": anomaly_table,
        }
        return self.to_pdf_bytes(title=title, sections=sections)

    def build_portfolio_report(
        self,
        title: str,
        portfolio_metrics: dict[str, float],
        positions: pd.DataFrame,
    ) -> bytes:
        """Build a portfolio status PDF report.

        Args:
            title: Report title.
            portfolio_metrics: Aggregated portfolio metrics.
            positions: Open positions table.

        Returns:
            Binary PDF report.
        """
        sections = {
            "Portfolio Metrics": {
                k: f"{v:.4f}" if isinstance(v, (float, int)) else v
                for k, v in portfolio_metrics.items()
            },
            "Open Positions": positions,
        }
        return self.to_pdf_bytes(title=title, sections=sections)

    def build_comparative_report(
        self,
        title: str,
        summary_table: pd.DataFrame,
        correlation_table: pd.DataFrame,
    ) -> bytes:
        """Build a comparative analysis PDF report.

        Args:
            title: Report title.
            summary_table: Comparative KPI table.
            correlation_table: Correlation matrix table.

        Returns:
            Binary PDF report.
        """
        sections = {
            "Comparative Summary": summary_table,
            "Correlation Matrix": correlation_table,
        }
        return self.to_pdf_bytes(title=title, sections=sections)
