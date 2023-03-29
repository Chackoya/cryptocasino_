"""
Views for the seeds APIs 


REF TO CONFIG ; 
https://www.django-rest-framework.org/api-guide/generic-views/#get_serializer_classself

"""
from rest_framework.response import Response

from rest_framework.decorators import action
from rest_framework import status
from rest_framework import viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from core.models import Seed#_BaseModel
from seeds import serializers
from django.db import transaction

class Seed_ViewSet(viewsets.ModelViewSet): #=> modelviewset for specific model; (opposite of standard view set )
    """View for manage wallets APIs. (expand this doc string for the swagger docs)"""
    serializer_class = serializers.SeedSerializer
    queryset = Seed.objects.all() #queryset => reps the objects that are available for this viewset; "A QuerySet is a collection of data from a database."
    
    #Following lines allow to specify that to use any of the ENDPOINTS from this view set:
    # a tokenauthentication type is required AND the user has to be authenticated; (error otherwise)
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]


    def get_allowed_methods(self):
        """
        Return the list of allowed HTTP methods for this view
        """
        allowed_methods = ['get', 'put']
        return [method.upper() for method in allowed_methods]

    def create(self, request, *args, **kwargs):
        """
        Override the create method to return 405 Method Not Allowed response
        """
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def get_queryset(self):
        """Retrieve trx hist for authenticated user."""
        return self.queryset.filter(user=self.request.user).order_by('-id') # Filtered by user & ordered by id 
    
    def get_serializer_class(self):
        """Return the serializer class for request."""
        #if self.action == 'list':#https://www.django-rest-framework.org/api-guide/viewsets/
        #    return serializers.WalletSerializer
        if self.action == 'change_server_seed':
            return serializers.ServerSeedSerializer
        
        return self.serializer_class
    
    
    @action(detail=False, methods=['get'], url_path='reveal_server_seed')
    def reveal_server_seed(self, request):
        #serializer = serializers.ServerSeedSerializer(data=request.data)
        #serializer.is_valid(raise_exception=True)  
        try:
            with transaction.atomic():
                print( )
                seed_user = Seed.objects.filter(user_id=request.user).first()
                hashed = seed_user.hash_server_seed()
                print("HASHED",hashed)
                original_server_seed = seed_user.reveal_server_seed()
                
        except Exception as e:
            print("Error reveal: ",e)
            return Response({
                'status': 'error',
                'message':"no modifications",
                "hashed_server_seed":seed_user.hash_server_seed()
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'status': 'success',
            'message': 'Server seed modified.',
            'server_seed':original_server_seed,
            'hashed_server_seed': seed_user.hash_server_seed(),
            
        }, status=status.HTTP_200_OK)
        
    
    
    @action(detail=False, methods=['put'], url_path='change_server_seed')
    def change_server_seed(self, request):
        serializer = serializers.ServerSeedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  
        
        try:
            with transaction.atomic():
                seed_user = Seed.objects.filter(user_id=request.user).first()
                seed_user.modify_server_seed()
            
        except Exception as e:
            print("Error: ",e)
            return Response({
                'status': 'error',
                'message':"no modifications",
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'status': 'success',
            'message': 'Server seed modified.',
            'hashed_server_seed': seed_user.hashed_server_seed_for_user,
            
        }, status=status.HTTP_200_OK)
    
    
    
    
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        #print(request.data)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)        
        #print(type(instance))
        
        """
        if 'client_seed' in request.data:
            field_to_update = request.data.get('client_seed')
            setattr(instance, 'client_seed', field_to_update)
            print("GG1")
            
        if 'server_seed' in request.data:
            to_update = request.data.get('server_seed')
            if to_update != "" and to_update!="string":
                print("to:",to_update)
                setattr(instance, 'server_seed', to_update)
                print("GG2")
        """
        """
        if 'visible' in request.data:
            to_update = request.data.get('server_seed')
            setattr(instance, 'server_seed', to_update)
        """
        # update specific fields
        fields_to_update = ['client_seed','visible']
        for field in fields_to_update:
            if field in request.data:
                field_value = request.data[field]
                if field_value != "" and field_value != "string":
                    if field_value:
                        setattr(instance, field, field_value)
   
        #print(str(instance), instance)
        #self.perform_update(serializer)
        instance.save()

        return Response(serializer.data)
