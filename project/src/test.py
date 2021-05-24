import argparse
import os
from pathlib import Path

import numpy as np
import torch as T
import torch.nn as nn
import yaml
from bagoftools.logger import Logger
from bagoftools.namespace import Namespace
from torch.utils.data import DataLoader
from torchsummary import summary

from data_loader import ImageFolder720p
from models.cae_32x32x32_zero_pad_bin import CAE
# from models.cae_16x16x16_zero_pad_bin import CAE
from utils import save_imgs

ROOT_EXP_DIR = Path(__file__).resolve().parents[1] / "experiments"

logger = Logger(__name__, colorize=True)


def test(cfg: Namespace) -> None:
    assert cfg.checkpoint not in [None, ""]
    print('device : ', cfg.device)
    print('available : ', T.cuda.is_available())
    print('test : ', cfg.device == "cpu" or (
        cfg.device == "cuda" and T.cuda.is_available()))
    assert cfg.device == "cpu" or (
        cfg.device == "cuda" and T.cuda.is_available())

    exp_dir = ROOT_EXP_DIR / cfg.exp_name
    os.makedirs(exp_dir / "out", exist_ok=True)
    cfg.to_file(exp_dir / "test_config.json")
    logger.info(f"[exp dir={exp_dir}]")

    model = CAE()
    model.load_state_dict(T.load(cfg.checkpoint))
    model.eval()
    if cfg.device == "cuda":
        model.cuda()
    logger.info(f"[model={cfg.checkpoint}] on {cfg.device}")

    dataloader = DataLoader(
        dataset=ImageFolder720p(cfg.dataset_path), batch_size=1, shuffle=cfg.shuffle
    )
    logger.info(f"[dataset={cfg.dataset_path}]")

    loss_criterion = nn.MSELoss()

    for batch_idx, data in enumerate(dataloader, start=1):
        img, patches, _ = data
        if cfg.device == "cuda":
            patches = patches.cuda()

        if batch_idx % cfg.batch_every == 0:
            pass

        out = T.zeros(6, 10, 3, 128, 128)
        avg_loss = 0

        for i in range(6):
            for j in range(10):
                x = patches[:, :, i, j, :, :].cuda()
                compressed = model.compress(x)

                y = model.decode(compressed)

                out[i, j] = y.data

                loss = loss_criterion(y, x)
                avg_loss += (1 / 60) * loss.item()

        logger.debug("[%5d/%5d] avg_loss: %f", batch_idx,
                     len(dataloader), avg_loss)

        # save output
        out = np.transpose(out, (0, 3, 1, 4, 2))
        out = np.reshape(out, (768, 1280, 3))
        out = np.transpose(out, (2, 0, 1))

        # save img decode
        save_imgs(
            imgs=out.unsqueeze(0),
            to_size=(3, 768, 1280),
            name=exp_dir / f"out/real_test_{batch_idx}.jpeg",
        )

        T.save(img, f'datasets/compressing/img_origin{batch_idx}')

        # save img origin
        save_imgs(
            imgs=img.unsqueeze(0),
            to_size=(3, 768, 1280),
            name=exp_dir / f"out/origin_test_{batch_idx}.jpeg",
        )
        y = T.cat((img[0], out), dim=2)
        print('y size :', y.unsqueeze(0).size())
        save_imgs(
            imgs=y.unsqueeze(0),
            to_size=(3, 768, 2 * 1280),
            name=exp_dir / f"out/test_{batch_idx}.png",
        )
    print('input size : ', x.size()[1:])
    summary(model, x.size()[1:])
    print(model)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    args = parser.parse_args()
    with open(args.config, "rt") as fp:
        cfg = Namespace(**yaml.safe_load(fp))

    test(cfg)
