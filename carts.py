import matplotlib.pyplot as plt
import io
import os
from aiogram.types import BufferedInputFile

def generate_trend_chart(history: list, indicator_name: str):
    """
    Extracts data for a specific indicator from history and creates a plot.
    """
    dates = []
    values = []

    # 1. Collect data points
    # We sort by date to make the line move correctly from left to right
    sorted_history = sorted(history, key=lambda x: x.get('date', ''))
    
    for entry in sorted_history:
        indicators = entry.get('indicators', [])
        for ind in indicators:
            # We look for a match in the name
            if indicator_name.lower() in ind.get('name', '').lower():
                try:
                    # Clean the value (remove units if any) and convert to float
                    val_str = ind.get('value', '').replace(',', '.')
                    val = float(''.join(c for c in val_str if c.isdigit() or c == '.'))
                    
                    dates.append(entry.get('date'))
                    values.append(val)
                except (ValueError, TypeError):
                    continue

    if len(values) < 2:
        return None # Not enough data for a trend line

    # 2. Create the plot
    plt.figure(figsize=(10, 6))
    plt.plot(dates, values, marker='o', linestyle='-', color='#2ecc71', linewidth=2)
    plt.title(f"Dynamic: {indicator_name}", fontsize=14, pad=20)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.tight_layout()

    # 3. Save to buffer instead of disk (faster/cleaner)
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close() # Important to prevent memory leaks

    return BufferedInputFile(buf.getvalue(), filename=f"{indicator_name}_trend.png")