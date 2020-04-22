import torch
import torch.nn as nn
import dgl.function as fn
from dgl.nn.pytorch import edge_softmax, GATConv
import numpy as np

# https://docs.dgl.ai/tutorials/hetero/1_basics.html#working-with-heterogeneous-graphs-in-dgl

from gat import GAT
from rgcn_hetero import RGCN

# from data import get_train_test_val_indices

def evaluate(logits, labels, train_idx, test_idx, val_idx):

    pred = logits.argmax(1)
    train_acc = (pred[train_idx] == labels[train_idx]).float().mean()
    val_acc = (pred[val_idx] == labels[val_idx]).float().mean()
    test_acc = (pred[test_idx] == labels[test_idx]).float().mean()

    return train_acc, val_acc, test_acc

def final_evaluation(model, g_labels, splits):
    train_idx, test_idx, val_idx = splits #get_train_test_val_indices(g_labels)
    labels = torch.tensor(g_labels)

    logits = model()
    evaluate(logits, labels, train_idx, test_idx, val_idx)
    logp = nn.functional.log_softmax(logits, 1)
    loss = nn.functional.nll_loss(logp[train_idx], labels[train_idx])

    train_acc, val_acc, test_acc = evaluate(logits, labels, train_idx, test_idx, val_idx)

    scores = {
        "loss": loss.item(),
        "train_acc": train_acc.item(),
        "val_acc": val_acc.item(),
        "test_acc": test_acc.item(),
    }

    print('Final Eval Loss %.4f, Train Acc %.4f, Val Acc %.4f, Test Acc %.4f' % (
        scores["loss"],
        scores["train_acc"],
        scores["val_acc"],
        scores["test_acc"],
    ))

    return scores


def train(model, g_labels, splits, epochs):

    train_idx, test_idx, val_idx = splits #get_train_test_val_indices(g_labels)
    labels = torch.tensor(g_labels)

    heldout_idx = test_idx.tolist() + val_idx.tolist()

    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

    best_val_acc = torch.tensor(0)
    best_test_acc = torch.tensor(0)

    for epoch in range(epochs):
        logits = model()

        train_acc, val_acc, test_acc = evaluate(logits, labels, train_idx, test_idx, val_idx)

        # pred = logits.argmax(1)
        # train_acc = (pred[train_idx] == labels[train_idx]).float().mean()
        # val_acc = (pred[val_idx] == labels[val_idx]).float().mean()
        # test_acc = (pred[test_idx] == labels[test_idx]).float().mean()

        logp = nn.functional.log_softmax(logits, 1)
        loss = nn.functional.nll_loss(logp[train_idx], labels[train_idx])
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

    return heldout_idx

def evaluate_no_classes(logits, labels):
    pred = logits.argmax(1)
    acc = (pred == labels).float().mean()
    return acc

def track_best(epoch, loss, train_acc, val_acc, test_acc, best_val_acc, best_test_acc):
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

def prepare_batch_no_classes(node_embeddings,
                             elem_embeder,
                             link_predictor,
                             indices,
                             batch_size,
                             negative_factor):
    K = negative_factor

    element_embeddings = elem_embeder(elem_embeder[indices])
    node_embeddings_batch = node_embeddings[indices]
    positive_batch = torch.cat([node_embeddings_batch, element_embeddings], 1)
    labels_pos = torch.ones(batch_size)

    node_embeddings_neg_batch = node_embeddings_batch.repeat(K, 1)
    negative_random = elem_embeder[np.random.randint(high=elem_embeder.n_elements, size=batch_size * K, replace=False)]
    negative_batch = torch.cat([node_embeddings_neg_batch, negative_random], 1)
    labels_neg = torch.zeros(batch_size * K)

    batch = torch.cat([positive_batch, negative_batch], 0)
    labels = torch.cat([labels_pos, labels_neg], 0)

    logits = link_predictor(batch)

    return logits, labels

def final_evaluation_no_classes(model, elem_embeder, link_predictor, splits):
    train_idx, test_idx, val_idx = splits

    node_embeddings = model()
    train_logits, train_labels = prepare_batch_no_classes(node_embeddings,
                                                          elem_embeder,
                                                          link_predictor,
                                                          train_idx,
                                                          train_idx.size,
                                                          1)

    test_logits, test_labels = prepare_batch_no_classes(node_embeddings,
                                                        elem_embeder,
                                                        link_predictor,
                                                        test_idx,
                                                        test_idx.size,
                                                        1)

    val_logits, val_labels = prepare_batch_no_classes(node_embeddings,
                                                      elem_embeder,
                                                      link_predictor,
                                                      val_idx,
                                                      val_idx.size,
                                                      1)

    train_acc, val_acc, test_acc = evaluate_no_classes(train_logits, train_labels), \
                                   evaluate_no_classes(test_logits, test_labels), \
                                   evaluate_no_classes(val_logits, val_labels)

    logp = nn.functional.log_softmax(train_logits, 1)
    loss = nn.functional.nll_loss(logp[train_idx], train_labels[train_idx])

    scores = {
        "loss": loss.item(),
        "train_acc": train_acc.item(),
        "val_acc": val_acc.item(),
        "test_acc": test_acc.item(),
    }

    print('Final Eval Loss %.4f, Train Acc %.4f, Val Acc %.4f, Test Acc %.4f' % (
        scores["loss"],
        scores["train_acc"],
        scores["val_acc"],
        scores["test_acc"],
    ))

    return scores

def train_no_classes(model, elem_embeder, link_predictor, splits, epochs):
    train_idx, test_idx, val_idx = splits

    # this is heldout because it was not used during training
    heldout_idx = test_idx.tolist() + val_idx.tolist()

    optimizer = torch.optim.SparseAdam(model.parameters(), lr=0.01)

    best_val_acc = torch.tensor(0)
    best_test_acc = torch.tensor(0)

    batch_size = 128
    K = 3 # negative oversampling factor

    for epoch in range(epochs):

        # since we train in batches, we need to iterate over the nodes
        # since indexes are sampled randomly, it is a little bit hard to make sure we cover all data
        # instead, we sample nodes the same number of times that there are different nodes in the dataset,
        # hoping to cover all the data
        num_batches = len(elem_embeder) // batch_size
        for batch_ind in range(num_batches):

            node_embeddings = model()

            random_batch = np.random.choice(train_idx, size=batch_size)

            train_logits, train_labels = prepare_batch_no_classes(node_embeddings,
                                                                  elem_embeder,
                                                                  link_predictor,
                                                                  random_batch,
                                                                  batch_size,
                                                                  K)

            train_acc = evaluate_no_classes(train_logits, train_labels)


            logp = nn.functional.log_softmax(train_logits, 1)
            loss = nn.functional.nll_loss(logp, train_labels)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            if batch_ind % 1 == 0:
                print("\r%d/%d batches complete" % (batch_ind, num_batches), end="")

        test_logits, test_labels = prepare_batch_no_classes(node_embeddings,
                                                            elem_embeder,
                                                            link_predictor,
                                                            test_idx,
                                                            test_idx.size,
                                                            1)

        val_logits, val_labels = prepare_batch_no_classes(node_embeddings,
                                                          elem_embeder,
                                                          link_predictor,
                                                          val_idx,
                                                          val_idx.size,
                                                          1)

        test_acc, val_acc = evaluate_no_classes(test_logits, test_labels), \
                                           evaluate_no_classes(val_logits, val_labels)

        track_best(epoch, loss, train_acc, val_acc, test_acc, best_val_acc, best_test_acc)