import matplotlib.pyplot as plt
from categorize import BillCategorizer
from sklearn.decomposition import PCA

class BillClusterVisualizer:
    def __init__(self, vectorizer, kmeans):
        self.vectorizer = vectorizer
        self.kmeans = kmeans

    def visualize(self, df):
        # Step 1: Transform text into TF-IDF features
        X = self.vectorizer.transform(df['Summary'])

        # Step 2: Reduce dimensions to 2D
        pca = PCA(n_components=2)
        X_reduced = pca.fit_transform(X.toarray())

        # Step 3: Get cluster labels
        labels = self.kmeans.labels_

        # Step 4: Plot
        plt.figure()

        # Separate noise (-1) and normal clusters
        noise_mask = (labels == -1)
        cluster_mask = (labels != -1)

        # Plot normal clusters
        scatter = plt.scatter(
            X_reduced[cluster_mask, 0],
            X_reduced[cluster_mask, 1],
            c=labels[cluster_mask],
            alpha=0.6
        )

        # Plot noise points as clear (hollow) circles
        plt.scatter(
            X_reduced[noise_mask, 0],
            X_reduced[noise_mask, 1],
            facecolors='none',  # makes them hollow
            edgecolors='black',  # outline color
            s=15,
            linewidths=0.25
            #label='Noise (-1)'
        )

        # Create legend for clusters
        legend1 = plt.legend(*scatter.legend_elements(), title="Clusters")
        plt.gca().add_artist(legend1)

        # Add legend entry for noise
        #plt.legend()

        plt.title("K-Means Clustering of Bills")  # fix title (was K-Means)
        plt.xlabel("PCA Component 1")
        plt.ylabel("PCA Component 2")

        plt.show()

if __name__ == "__main__":
    categorizer = BillCategorizer(n_clusters=5)
    df = categorizer.categorize_bills(
        input_csv="../data/new_data/congressional_votes_cleaned.csv",
        output_csv="../data/new_data/bills_categorized.csv"
    )
    viz = BillClusterVisualizer(categorizer.vectorizer, categorizer.kmeans)
    viz.visualize(df)