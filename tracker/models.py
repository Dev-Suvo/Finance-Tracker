from django.db import models
import uuid

class BaseModel(models.Model):
    created_at = models.DateField(auto_now_add=True)
    creation_time = models.TimeField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    updation_time = models.TimeField(auto_now=True)


    class Meta:
        abstract = True



# class User(models.Model):





# class Wallet(BaseModel):
    



class Transaction(BaseModel):
    transaction_id = models.UUIDField(default=uuid.uuid4,primary_key=True ,editable= False)
    description = models.CharField(max_length= 100)
    amount = models.DecimalField(max_digits=10,decimal_places=2)
