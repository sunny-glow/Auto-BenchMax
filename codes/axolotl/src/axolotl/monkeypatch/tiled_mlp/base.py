"""
TiledMLP support for DDP, FSDP, and single GPU
"""

import threading
from typing import List

import torch


class DeepSpeedTiledMLPMoE(torch.autograd.Function):
    @staticmethod
    def forward(
        ctx,
        fn,
        self,
        x,
        shards,
        compute_params,
    ) -> torch.Tensor:
        ctx.fn = fn
        ctx.self = self
        ctx.shards = shards
        ctx.compute_params = [p for p in compute_params if p.requires_grad]
        ctx.save_for_backward(x)

        # Use dim=-2 to shard sequence/token dimension for both 3D (batch, seq, hidden)
        # and 2D (tokens, hidden) tensors (e.g., MoE expert inputs)
        shard_dim = x.ndim - 2  # 1 for 3D, 0 for 2D
        x_shards = list(torch.chunk(x, chunks=shards, dim=shard_dim))
        with torch.no_grad():
            output_shards = [fn(self, x_shard) for x_shard in x_shards]

        ctx.is_tuple_output = isinstance(output_shards[0], tuple)
        ctx.shard_dim = shard_dim
        if isinstance(output_shards[0], tuple):
            tuple_dim_idx = [1, 0]
            output_unsharded = tuple(
                torch.cat(
                    [output_shard[i] for output_shard in output_shards],
                    dim=tuple_dim_idx[i],
                )
                for i in range(len(output_shards[0]))
            )
        else:
            output_unsharded = torch.cat(output_shards, dim=shard_dim)

        return output_unsharded

    @staticmethod
    def backward(ctx, *grads) -> torch.Tensor:
        fn = ctx.fn
        (x,) = ctx.saved_tensors
        self = ctx.self
        shards = ctx.shards
        compute_params = ctx.compute_params
        is_tuple_output = ctx.is_tuple_output
        shard_dim = ctx.shard_dim

        x_requires_grad = x.requires_grad
        x = x.detach()
        # detach() unsets `x.requires_grad`, so restore it
        x.requires_grad_(x_requires_grad)

        incoming_grad = grads[0]
        x_grad = torch.zeros_like(x)
        x_shards = list(torch.chunk(x, chunks=shards, dim=shard_dim))

        shard_step = x_shards[0].numel()
        for i, x_shard in enumerate(x_shards):
            # Tell deepspeed not to add a new grad to its ipg bucket until the last shard is run
            if compute_params is not None:
                if i + 1 < shards:
                    for param in compute_params:
                        param.ds_grad_is_ready = False
                else:
                    # last shard, can add the grad
                    for param in compute_params:
                        param.ds_grad_is_ready = True

            x_shard.requires_grad_(x_requires_grad)

            shard_offset = i * shard_step
            x_shard.grad = (
                x_grad.view(-1)
                .narrow(0, shard_offset, x_shard.numel())
                .view_as(x_shard)
            )
            incoming_grad_shard = (
                incoming_grad.view(-1)
                .narrow(0, shard_offset, x_shard.numel())
                .view_as(x_shard)
            )
            with torch.enable_grad():
                output = fn(self, x_shard)
            if is_tuple_output:
                torch.autograd.backward(output[0], incoming_grad_shard)
            else:
                torch.autograd.backward(output, incoming_grad_shard)

        return (None, None, x_grad, None, None)


class TiledMLP(torch.autograd.Function):
    """
    TiledMLP implementation using gradient hooks
    """

    @staticmethod
    def forward(
        ctx,
        fn,
        self,
        x,
        shards,
        compute_params,
    ) -> torch.Tensor:
        ctx.fn = fn
        ctx.self = self
        ctx.shards = shards
        ctx.compute_params = [p for p in compute_params if p.requires_grad]
        ctx.save_for_backward(x)

        # Use dim=-2 to shard sequence/token dimension for both 3D (batch, seq, hidden)
        # and 2D (tokens, hidden) tensors (e.g., MoE expert inputs)
        shard_dim = x.ndim - 2  # 1 for 3D, 0 for 2D
        x_shards = list(torch.chunk(x, chunks=shards, dim=shard_dim))
        with torch.no_grad():
            output_shards = [fn(self, x_shard) for x_shard in x_shards]
        ctx.is_tuple_output = isinstance(output_shards[0], tuple)
        ctx.shard_dim = shard_dim
        if isinstance(output_shards[0], tuple):
            tuple_dim_idx = [1, 0]
            output_unsharded = tuple(
                torch.cat(
                    [output_shard[i] for output_shard in output_shards],
                    dim=tuple_dim_idx[i],
                )
                for i in range(len(output_shards[0]))
            )
        else:
            output_unsharded = torch.cat(output_shards, dim=shard_dim)

        return output_unsharded

    @staticmethod
    def backward(ctx, *grads) -> torch.Tensor:
        fn = ctx.fn
        (x,) = ctx.saved_tensors
        self = ctx.self
        shards = ctx.shards
        compute_params = ctx.compute_params
        is_tuple_output = ctx.is_tuple_output
        shard_dim = ctx.shard_dim

        x_requires_grad = x.requires_grad
        x = x.detach()
        x.requires_grad_(x_requires_grad)

        incoming_grad = grads[0]
        x_grad = torch.zeros_like(x)
        x_shards = list(torch.chunk(x, chunks=shards, dim=shard_dim))

        # Create a gradient accumulator for parameters
        # Install hooks ONCE before the loop (not per-shard)
        grad_accumulator = GradientAccumulator(compute_params, shards, dtype=x.dtype)
        grad_accumulator.install_hooks()

        shard_step = x_shards[0].numel()
        for i, x_shard in enumerate(x_shards):
            x_shard.requires_grad_(x_requires_grad)

            shard_offset = i * shard_step
            x_shard.grad = (
                x_grad.view(-1)
                .narrow(0, shard_offset, x_shard.numel())
                .view_as(x_shard)
            )
            incoming_grad_shard = (
                incoming_grad.view(-1)
                .narrow(0, shard_offset, x_shard.numel())
                .view_as(x_shard)
            )

            with torch.enable_grad():
                output = fn(self, x_shard)
            if is_tuple_output:
                torch.autograd.backward(output[0], incoming_grad_shard)
            else:
                torch.autograd.backward(output, incoming_grad_shard)

        # Finalize gradients and clean up hooks
        grad_accumulator.finalize_and_cleanup()

        return (None, None, x_grad, None, None)


class GradientAccumulator:
    """
    Manual gradient accumulator for TiledMLP with configurable precision.
    Accumulates gradients from all shards (sum, not average).

    Fixed implementation: hooks are installed once and track shard count internally.
    """

    def __init__(
        self,
        params: List[torch.nn.Parameter],
        total_shards: int,
        dtype: torch.dtype | None = None,
    ):
        self.params = params
        self.total_shards = total_shards
        self.grad_accumulation_dtype = dtype or torch.float32
        self.accumulated_grads = {}
        self.hooks = []
        self.lock = threading.Lock()
        self.call_counts = {}  # Track how many times each param's hook was called

        # Initialize accumulated gradients in the specified dtype
        for param in self.params:
            self.call_counts[id(param)] = 0
            if param.grad is not None:
                self.accumulated_grads[param] = param.grad.to(
                    self.grad_accumulation_dtype
                )
                param.grad = None
            else:
                self.accumulated_grads[param] = torch.zeros_like(
                    param, dtype=self.grad_accumulation_dtype
                )

    def install_hooks(self):
        """Install gradient hooks once (not per-shard)"""

        def create_hook(param):
            def hook(grad):
                with self.lock:
                    # Accumulate gradient in higher precision (sum, not average)
                    grad_to_accum_dtype = grad.to(self.grad_accumulation_dtype)
                    self.accumulated_grads[param] += grad_to_accum_dtype

                    # Track call count for this param
                    self.call_counts[id(param)] += 1

                    # Return None to prevent PyTorch from accumulating the raw gradient
                    # We'll set param.grad manually in finalize_and_cleanup
                    return None

            return hook

        # Install hooks on all parameters ONCE
        for param in self.params:
            if param.requires_grad:
                hook = param.register_hook(create_hook(param))
                self.hooks.append(hook)

    def finalize_and_cleanup(self):
        """Assign accumulated gradients to params and remove hooks"""
        # First remove hooks to prevent any further accumulation
        for hook in self.hooks:
            hook.remove()
        self.hooks.clear()

        # Assign accumulated gradients to params
        for param in self.params:
            if param in self.accumulated_grads:
                param.grad = self.accumulated_grads[param].to(param.dtype)

        del self.accumulated_grads
        del self.call_counts
