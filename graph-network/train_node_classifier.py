import torch
import torch.nn as nn
import dgl.function as fn
from dgl.nn.pytorch import edge_softmax, GATConv
import numpy as np

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
    """
    Training procedure for the model with node classifier.
    :param model:
    :param g_labels:
    :param splits:
    :param epochs:
    :return:
    """

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

        torch.save({
            'm': model.state_dict(),
            "epoch": epoch
        }, "saved_state.pt")

    return heldout_idx

def training_procedure(dataset, model, params, EPOCHS, restore_state):
    m = model(dataset.g,
              num_classes=dataset.num_classes,
              produce_logits=True,
              **params)

    if restore_state:
        checkpoint = torch.load("saved_state.pt")
        m.load_state_dict(checkpoint['m'])
        print(f"Restored from epoch {checkpoint['epoch']}")
        checkpoint = None

    try:
        train(m, dataset.labels, dataset.splits, EPOCHS)
    except KeyboardInterrupt:
        print("Training interrupted")
    finally:
        m.eval()
        scores = final_evaluation(m, dataset.labels, dataset.splits)

    return m, scores