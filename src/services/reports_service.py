from __future__ import annotations

from typing import Any

import pandas as pd


class ReportsService:
    def to_csv_bytes(self, df: pd.DataFrame) -> bytes:
        return df.to_csv(index=True).encode("utf-8")

    def to_png_bytes(self, fig: Any) -> bytes:
        if hasattr(fig, "to_image"):
            try:
                return fig.to_image(format="png")
            except Exception:
                return b""
        return b""

    def _minimal_pdf_from_lines(self, lines: list[str]) -> bytes:
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
        sections = {
            "Comparative Summary": summary_table,
            "Correlation Matrix": correlation_table,
        }
        return self.to_pdf_bytes(title=title, sections=sections)
