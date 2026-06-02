from django.db import models
import uuid

class BaseModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, primary_key= True, editable= False)
    created_at = models.DateField(auto_now= True)
    updated_at = models.DateField(auto_now_add= True)

    class Meta:
        abstract = True



# class User(models.Model):





# class Wallet(BaseModel):
    



class Transaction(BaseModel):
    description = models.CharField(max_length= 100)
    amount = models.FloatField()
