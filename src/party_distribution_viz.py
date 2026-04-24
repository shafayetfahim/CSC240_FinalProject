import pandas as pd
import matplotlib.pyplot as plt

def plot_party_distribution(csv_path="../data/representatives_cleaned.csv"):
    df = pd.read_csv(csv_path)

    party_counts = df['party_code'].value_counts()

    color_map = {
        "D": "blue",
        "R": "red",
        "Other": "gray"
    }

    labels = list(party_counts.index)
    sizes = party_counts.values
    colors = [color_map.get(label, "black") for label in labels]

    plt.figure()

    # No labels inside wedges
    wedges, texts, autotexts = plt.pie(
        sizes,
        labels=None,
        autopct='%1.1f%%',
        colors=colors,
        startangle=90
    )

    # Build legend labels with counts
    legend_labels = [
        f"{label} ({count})"
        for label, count in zip(labels, sizes)
    ]

    plt.legend(
        wedges,
        legend_labels,
        title="Party",
        loc="center left",
        bbox_to_anchor=(1, 0.5)
    )

    plt.axis('equal')
    plt.title("Representative Party Distribution")
    plt.show()

if __name__ == "__main__":
    plot_party_distribution()