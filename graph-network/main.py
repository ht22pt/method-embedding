#%%
import sys
from data import load_data, get_train_test_val_indices
from graphtools import *
import numpy as np
from models import *
from sklearn.model_selection import ParameterGrid
from datetime import datetime
from params import gat_params, rgcn_params

node_path = "/home/ltv/data/datasets/source_code/python-source-graph/normalized_sourcetrail_nodes.csv"
edge_path = "/home/ltv/data/datasets/source_code/python-source-graph/non-ambiguous_edges.csv"
# node_path = "/home/ltv/data/datasets/source_code/sample-python/normalized_sourcetrail_nodes.csv"
# edge_path = "/home/ltv/data/datasets/source_code/sample-python/edges.csv"



#%%
print("Loading data...", end="")
nodes, edges = load_data(node_path, edge_path)
print("done")
# print("Creating graph...", end="")
# g, labels = create_graph(nodes, edges)
# print("done")

print("Using GPU:", torch.cuda.is_available())

#%%

models = {
    GAT: gat_params,
    # EntityClassify: rgcn_params
}

def train(model, g_labels):

    train_idx, test_idx, val_idx = get_train_test_val_indices(g_labels)
    labels = torch.tensor(g_labels)

    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

    best_val_acc = torch.tensor(0)
    best_test_acc = torch.tensor(0)

    for epoch in range(300):
        logits = model()
        logp = nn.functional.log_softmax(logits, 1)
        # we only compute loss for labeled nodes
        loss = nn.functional.nll_loss(logp[train_idx], labels[train_idx])

        pred = logits.argmax(1)
        train_acc = (pred[train_idx] == labels[train_idx]).float().mean()
        val_acc = (pred[val_idx] == labels[val_idx]).float().mean()
        test_acc = (pred[test_idx] == labels[test_idx]).float().mean()

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if best_val_acc < val_acc:
            best_val_acc = val_acc
            best_test_acc = test_acc

        print('Epoch %d, Loss %.4f, Train Acc %.4f, Val Acc %.4f (Best %.4f), Test Acc %.4f (Best %.4f)' % (
            epoch,
            loss.item(),
            train_acc.item(),
            val_acc.item(),
            best_val_acc.item(),
            test_acc.item(),
            best_test_acc.item(),
        ))

#%%


for model, param_grid in models.items():
    for params in ParameterGrid(param_grid):
        dateTimeObj = str(datetime.now())
        print("\n\n")
        print(dateTimeObj)
        print("Model: {}, Params: {}".format(model.__name__, params))

        if model.__name__ == "GAT":
            g, labels = create_graph(nodes, edges)
        elif model.__name__ == "EntityClassify":
            g, labels = create_hetero_graph(nodes, edges)
        else:
            raise Exception("Unknown model: {}".format(model.__name__))

        m = model(g, num_classes=np.unique(labels).size, **params)

        train(m, labels)

        torch.save(m, open("{} {}".format(model.__name__, dateTimeObj), "wb"))


