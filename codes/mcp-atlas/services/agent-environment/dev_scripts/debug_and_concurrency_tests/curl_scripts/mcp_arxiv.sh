#!/bin/bash

# Array of 15 academic search queries
search_queries=(
  "machine learning neural networks"
  "quantum computing algorithms"
  "computer vision deep learning"
  "natural language processing transformers"
  "reinforcement learning robotics"
  "blockchain consensus mechanisms"
  "cryptography zero knowledge proofs"
  "artificial intelligence ethics"
  "computational biology genomics"
  "statistical learning theory"
  "graph neural networks"
  "optimization algorithms"
  "distributed systems consensus"
  "information theory coding"
  "mathematical physics"
)

# Array of 13 known arXiv paper IDs
paper_ids=(
  "1706.03762"  # Attention Is All You Need (Transformers)
  "1312.6114"   # Auto-Encoding Variational Bayes (VAE)
  # "1406.2661"   # Generative Adversarial Networks (GANs)  
  # the commented-out ones have conversion error after downloading, are unusable
  # "1801.04406"  # Which Training Methods for GANs
  "1512.03385"  # Deep Residual Learning for Image Recognition (ResNet)
  "1409.1556"   # Very Deep Convolutional Networks (VGG)
  "1511.06434"  # Unsupervised Representation Learnin
  "1602.07261"  # Inception-v4, Inception-ResNet
  # "1707.06347"  # Proximal Policy Optimization Algorithms
  "1905.11946"  # EfficientNet
  # "2010.11929"  # An Image is Worth 16x16 Words (Vision Transformer)
  "1909.11942"  # ALBERT: A Lite BERT 
  "2005.14165"  # Language Models are Few-Shot Learners
  # "1810.04805"  # BERT
  "1207.0580"   # Improving neural networks by preventing co-adaptation of feature detectors
  "1409.4842"   # Going Deeper with Convolutions (GoogLeNet/Inception)
  # "1502.03167"  # Batch Normalization: Accelerating Deep Network Training
  # "1412.6980"   # Adam: A Method for Stochastic Optimization
  "1505.04597"  # U-Net: Convolutional Networks for Biomedical Image Segmentation
  "1703.06870"  # Mask R-CNN
  # "1506.02640"  # You Only Look Once: Unified, Real-Time Object Detection (YOLO)
  # "1409.0473"   # Neural Machine Translation by Jointly Learning to Align and Translate
  # "1704.04861"  # MobileNets: Efficient Convolutional Neural Networks for Mobile Vision Applications
  # "1709.01507"  # Squeeze-and-Excitation Networks
)

# Randomly choose between search (0) or read_paper (1)
operation=$((RANDOM % 2))

if [ $operation -eq 0 ]; then
  # Search operation
  random_index=$((RANDOM % ${#search_queries[@]}))
  selected_query="${search_queries[$random_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H "Content-Type: application/json" \
    -d '{
      "tool_name": "arxiv_search_papers",
      "tool_args": {
        "query": "'"$selected_query"'",
        "max_results": 2
      }
    }'
else
  # Read paper operation (download first, then read)
  random_index=$((RANDOM % ${#paper_ids[@]}))
  selected_paper_id="${paper_ids[$random_index]}"
  
  # First download the paper
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H "Content-Type: application/json" \
    -d '{
      "tool_name": "arxiv_download_paper",
      "tool_args": {
        "paper_id": "'"$selected_paper_id"'"
      }
    }'
  
  # Then read the paper
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H "Content-Type: application/json" \
    -d '{
      "tool_name": "arxiv_read_paper",
      "tool_args": {
        "paper_id": "'"$selected_paper_id"'"
      }
    }'
fi 