"""Synthetic evaluation fixture: transfer-core 2.2 service behavior."""


class TransferRejected(ValueError):
    pass


class TransferService:
    def __init__(self, repository, config):
        self.repository = repository
        self.pieces_per_box = config["pieces_per_box"]

    def create(self, source, destination, sku, boxes, request_key):
        if isinstance(boxes, bool) or not isinstance(boxes, int) or boxes <= 0:
            raise TransferRejected("positive integer box count required")
        if source == destination:
            raise TransferRejected("source and destination must differ")
        if not request_key.strip():
            raise TransferRejected("request key required")
        pieces = boxes * self.pieces_per_box
        with self.repository.transaction():
            if self.repository.take_stock(source, sku, pieces) != 1:
                raise TransferRejected("source stock unavailable")
            transfer_id = self.repository.insert_transfer(
                request_key, source, destination, sku, pieces
            )
        return {"id": transfer_id, "status": "in_transit", "pieces": pieces}

    def receive(self, transfer_id, destination):
        with self.repository.transaction():
            transfer = self.repository.get_transfer(transfer_id)
            if transfer is None:
                raise TransferRejected("transfer not found")
            if transfer["destination_warehouse"] != destination:
                raise TransferRejected("destination mismatch")
            if transfer["status"] != "in_transit":
                raise TransferRejected("transfer is not awaiting receipt")
            if self.repository.mark_received(transfer_id) != 1:
                raise TransferRejected("receipt state changed")
            self.repository.add_stock(destination, transfer["sku"], transfer["pieces"])
        return {"id": transfer_id, "status": "received"}
