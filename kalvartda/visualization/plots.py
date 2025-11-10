import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from typing import List, Dict, Any

class TDAVisualizer:
    def __init__(self, theme: str = "plotly_white"):
        self.theme = theme
    
    def create_persistence_diagram(self, features: List[Dict]) -> go.Figure:
        """Create interactive persistence diagram"""
        df = pd.DataFrame(features)
        
        if df.empty:
            return self._empty_plot("No features found")
        
        fig = px.scatter(
            df, 
            x='birth', 
            y='death',
            color='dimension',
            size='persistence',
            hover_data=['birth', 'death', 'persistence'],
            title="Persistence Diagram",
            template=self.theme
        )
        
        # Add diagonal line
        max_val = max(df['death'].max(), df['birth'].max())
        fig.add_shape(
            type="line",
            x0=0, y0=0, x1=max_val, y1=max_val,
            line=dict(dash="dash", color="gray")
        )
        
        fig.update_layout(
            xaxis_title="Birth Time",
            yaxis_title="Death Time",
            showlegend=True
        )
        
        return fig
    
    def create_before_after_comparison(self, before_features: List[Dict], 
                                     after_features: List[Dict], 
                                     wasserstein_dist: float) -> go.Figure:
        """Create side-by-side comparison"""
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("Before Fire", "After Fire"),
            specs=[[{"type": "scatter"}, {"type": "scatter"}]]
        )
        
        # Before state
        if before_features:
            before_df = pd.DataFrame(before_features)
            fig.add_trace(
                go.Scatter(
                    x=before_df['birth'],
                    y=before_df['death'],
                    mode='markers',
                    marker=dict(
                        size=before_df['persistence'] * 20,
                        color=before_df['dimension'],
                        colorscale='viridis'
                    ),
                    name="Before"
                ),
                row=1, col=1
            )
        
        # After state
        if after_features:
            after_df = pd.DataFrame(after_features)
            fig.add_trace(
                go.Scatter(
                    x=after_df['birth'],
                    y=after_df['death'],
                    mode='markers',
                    marker=dict(
                        size=after_df['persistence'] * 20,
                        color=after_df['dimension'],
                        colorscale='viridis'
                    ),
                    name="After"
                ),
                row=1, col=2
            )
        
        fig.update_layout(
            title=f"TDA Comparison (Wasserstein Distance: {wasserstein_dist:.4f})",
            template=self.theme
        )
        
        return fig
    
    def _empty_plot(self, message: str) -> go.Figure:
        """Create empty plot with message"""
        fig = go.Figure()
        fig.add_annotation(
            x=0.5, y=0.5,
            text=message,
            showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            template=self.theme
        )
        return fig